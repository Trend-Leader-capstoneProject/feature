"""Internal HOLD staging boundary only; no operational store is configured."""

import json
import os
import stat
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path

import fr_b02b_observation as observation
from fr_b02b_a1_adapter import A1InspectionError, A1Snapshot, _load_a1_snapshot_bytes
from fr_b02b_observation import VerifiedObservation

PENDING_KEYS = frozenset({
    "local_evidence_id", "reviewer_sid", "review_result", "decision_reason",
    "reviewed_at_utc", "publish_authorization", "a1_archive_sha256",
    "observation_sha256", "index_sha256",
})


class StagingError(ValueError):
    """Safe staging failure; all remnants are unusable HOLD."""


@dataclass(frozen=True)
class StagedReview:
    staging_dir: Path
    state: str = field(default="HOLD", init=False)
    publish_authorization: str = field(default="NONE", init=False)


@dataclass(frozen=True)
class MirroredStagedReview:
    """Internal copy-verification receipt, never a registration reference."""

    primary_staging_dir: Path
    backup_staging_dir: Path
    sha256: tuple[tuple[str, str], ...]
    state: str = field(default="HOLD", init=False)
    publish_authorization: str = field(default="NONE", init=False)


@dataclass(frozen=True)
class RestoredStagedReview(MirroredStagedReview):
    """Verified internal round trip; still HOLD, never a valid registration."""

    restored_staging_dir: Path


def _validated_files(evidence: VerifiedObservation, pending_bytes: bytes) -> dict[str, bytes]:
    """Do not trust the snapshot type/name as proof of validation."""
    try:
        if (not isinstance(evidence, VerifiedObservation)
                or not isinstance(evidence.a1_snapshot, A1Snapshot)
                or not isinstance(evidence.record_bytes, bytes)
                or not isinstance(evidence.index_bytes, bytes)
                or len(evidence.record_bytes) > observation.MAX_RECORD_BYTES
                or len(evidence.index_bytes) > observation.MAX_RECORD_BYTES
                or not isinstance(pending_bytes, bytes)
                or len(pending_bytes) > observation.MAX_RECORD_BYTES):
            raise ValueError("invalid staging input")
        snapshot = _load_a1_snapshot_bytes(evidence.a1_snapshot.archive_bytes)
        if snapshot != evidence.a1_snapshot:
            raise ValueError("unverified A1 display fields")
        value = json.loads(pending_bytes.decode("utf-8"))
        if (not isinstance(value, dict) or set(value) != PENDING_KEYS
                or any(not isinstance(item, str) for item in value.values())
                or any(not item for key, item in value.items() if key != "decision_reason")
                or observation.canonical_bytes(value) != pending_bytes):
            raise ValueError("invalid pending metadata")
        record = observation._validate_records(snapshot, evidence.record_bytes,
                                                evidence.index_bytes, value["local_evidence_id"])
        if record != evidence.record:
            raise ValueError("unverified observation display fields")
        if (value["publish_authorization"] != "NONE"
                or value["review_result"] not in ("ACCEPTED", "HOLD", "REJECTED")
                or len(value["decision_reason"]) > 500
                or (value["review_result"] != "ACCEPTED" and not value["decision_reason"].strip())
                or observation._timestamp(value["reviewed_at_utc"])
                < observation._timestamp(record["record_created_at_utc"])):
            raise ValueError("invalid pending decision")
        files = {"a1_archive.zip": snapshot.archive_bytes,
                 "observation.json": evidence.record_bytes, "index.json": evidence.index_bytes,
                 "pending_review.json": pending_bytes}
        for field_name, file_name in (("a1_archive_sha256", "a1_archive.zip"),
                                      ("observation_sha256", "observation.json"),
                                      ("index_sha256", "index.json")):
            if value[field_name] != observation.digest(files[file_name]):
                raise ValueError("unverified file digest")
        return files
    except (ValueError, UnicodeError, RecursionError, A1InspectionError):
        raise StagingError("invalid staging bytes or decision; remnants remain HOLD") from None


class ProtectedEvidenceStore:
    """HOLD-only primitive. Tests supply root/protection, never the public CLI.

    No ACL provisioning, rename to registrations/, completion marker, backup or
    automatic cleanup/recovery is provided. Path checks do not certify all hostile
    filesystem races; native protection/locking must be proven before deployment.
    """

    _native_boundary = None

    def __init__(self, root: Path, verify_protection: Callable[[Path], bool]):
        self.root = root
        self.verify_protection = verify_protection

    @property
    def staging_roots(self) -> tuple[Path, ...]:
        return (self.root,)

    def stage(self, evidence: VerifiedObservation, pending_bytes: bytes, *,
              revalidate_input: Callable[[], None]) -> StagedReview:
        files = _validated_files(evidence, pending_bytes)
        try:
            if not isinstance(self.root, Path) or not self.root.is_absolute():
                raise StagingError("unconfigured staging root; remnants remain HOLD")
            root = self._checked(self.root, directory=True)
            self._revalidate(revalidate_input)
            event_id = observation._event_id(evidence.record["evidence_id"])
            staging = root / (".review-staging-" + event_id)
            # Exclusive per-evidence reservation: a collision or failed previous
            # attempt is investigated manually, never retried with a new ID.
            self._create_staging(staging)
            self._checked(staging, directory=True)
            for name, raw in files.items():
                self._checked(root, directory=True)
                self._checked(staging, directory=True)
                self._revalidate(revalidate_input)
                self._write_file(staging / name, raw)
                self._checked(staging / name, directory=False)
            if {path.name for path in staging.iterdir()} != set(files):
                raise StagingError("unexpected staging contents; remnants remain HOLD")
            for name, expected in files.items():
                path = self._checked(staging / name, directory=False)
                actual = self._read_copy(path, len(expected) + 1)
                if actual != expected:
                    raise StagingError("staging byte mismatch; remnants remain HOLD")
                self._checked(path, directory=False)
            self._checked(root, directory=True)
            self._checked(staging, directory=True)
            self._revalidate(revalidate_input)
            return StagedReview(staging)
        except StagingError:
            raise
        except (OSError, observation.ObservationError):
            raise StagingError("staging path/write failure; remnants remain HOLD") from None

    @staticmethod
    def _revalidate(callback: Callable[[], None]) -> None:
        try:
            callback()
        except (OSError, ValueError):
            raise StagingError("input/authority revalidation failed; remnants remain HOLD") from None

    def _create_staging(self, path: Path) -> None:
        path.mkdir(exist_ok=False)

    def _write_file(self, path: Path, raw: bytes) -> None:
        _write_exclusive(path, raw)

    def _read_copy(self, path: Path, limit: int) -> bytes:
        before = path.stat()

        def identity(info):
            return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)

        with path.open("rb") as handle:
            if identity(os.fstat(handle.fileno())) != identity(before):
                raise StagingError("opened copy identity mismatch; HOLD")
            raw = handle.read(limit)
            if identity(os.fstat(handle.fileno())) != identity(before):
                raise StagingError("opened copy changed; HOLD")
        return raw

    def _checked(self, path: Path, *, directory: bool) -> Path:
        path = observation._safe_local_path(path)
        info = path.lstat()
        valid = (stat.S_ISDIR(info.st_mode) if directory else
                 stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        if not valid or not info.st_ino:
            raise StagingError("unsafe staging path; remnants remain HOLD")
        try:
            protected = self.verify_protection(path)
        except (OSError, ValueError):
            raise StagingError("staging protection failure; remnants remain HOLD") from None
        if protected is not True:
            raise StagingError("staging protection unverified; remnants remain HOLD")
        return path


class MirroredEvidenceStore:
    """C/E HOLD staging coordinator; operating adapters are deliberately absent.

    A trusted deployment must supply both pre-existing protected roots, a layout
    verifier (approved C/E objects, independent disks/volumes and native boundary
    protection), and a protected global exclusive section held across ALL work.
    None is inferred from a drive letter or provisioned here. Tests inject those
    proofs; temporary I/O does not prove Windows ACLs or hostile-race resistance.
    The existing path-based primitive still requires a proven native boundary
    before deployment. Optional restore verification never completes registration.
    """

    def __init__(self, primary: ProtectedEvidenceStore | None = None,
                 backup: ProtectedEvidenceStore | None = None, *,
                 verify_layout: Callable[[Path, Path], bool] | None = None,
                 exclusive_section: Callable[[], AbstractContextManager] | None = None):
        self.primary, self.backup = primary, backup
        self.verify_layout = verify_layout
        self.exclusive_section = exclusive_section

    @property
    def staging_roots(self) -> tuple[Path, ...]:
        if self.primary is None or self.backup is None:
            return ()
        return (self.primary.root, self.backup.root)

    def stage(self, evidence: VerifiedObservation, pending_bytes: bytes, *,
              revalidate_input: Callable[[], None],
              restore_store: ProtectedEvidenceStore | None = None,
              inventory_store=None, registration_core=None) -> MirroredStagedReview:
        files = _validated_files(evidence, pending_bytes)
        if (not isinstance(self.primary, ProtectedEvidenceStore)
                or not isinstance(self.backup, ProtectedEvidenceStore)
                or not callable(self.verify_layout) or not callable(self.exclusive_section)):
            raise StagingError("protected C/E configuration or global lock missing; HOLD")
        stores = (self.primary, self.backup)
        roots = tuple(store.root for store in stores)
        if (any(not isinstance(root, Path) or not root.is_absolute() for root in roots)
                or roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0])):
            raise StagingError("overlapping or unconfigured protected roots; HOLD")
        event_id = observation._event_id(evidence.record["evidence_id"])
        staging = tuple(root / (".review-staging-" + event_id) for root in roots)
        all_stores = (*stores, restore_store) if restore_store is not None else stores
        if any(not isinstance(store, ProtectedEvidenceStore) for store in all_stores):
            raise StagingError("invalid restore store; HOLD")
        providers = tuple(store._native_boundary for store in all_stores)
        if registration_core is not None:
            from fr_b02b_registration import RegistrationCore
            if not isinstance(registration_core, RegistrationCore):
                raise StagingError("unverified registration completion plan; HOLD")
            registration_core.require_environment(stores, restore_store, evidence, pending_bytes)
        if any(provider is not None for provider in providers):
            provider = next(item for item in providers if item is not None)
            if (any(item is not provider for item in providers)
                    or self.exclusive_section != provider.exclusive_section
                    or self.verify_layout != provider.verify_layout
                    or roots != (provider.policy.primary, provider.policy.backup)
                    or any(store.root not in roots for store in all_stores)):
                raise StagingError("mixed Native I/O or bypassed global Gate; HOLD")
        if inventory_store is not None:
            from fr_b02b_inventory import ProtectedInventory
            if (restore_store is None or not isinstance(inventory_store, ProtectedInventory)
                    or not providers or providers[0] is None
                    or inventory_store.boundary is not providers[0]):
                raise StagingError("inventory requires restored C/E within the same Native Gate; HOLD")
            inventory_store.ensure_creation_available()
        restorer = None
        if restore_store is not None:
            from fr_b02b_restore import BackupRestoreVerifier
            restorer = BackupRestoreVerifier(restore_store, evidence, pending_bytes, roots)
        digests = tuple((name, observation.digest(raw)) for name, raw in files.items())
        identities = {}

        def identity(info):
            return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)

        def pin(path):
            info = path.lstat()
            current = identity(info)
            if (not info.st_ino or current != identities.setdefault(path, current)):
                raise StagingError("protected object identity changed; HOLD")
            return current

        def boundaries():
            if any(item is not None for item in providers):
                if (any(store._native_boundary is not provider for store in all_stores)
                        or self.exclusive_section != provider.exclusive_section
                        or self.verify_layout != provider.verify_layout):
                    raise StagingError("Native I/O/Gate binding changed during operation; HOLD")
            for store, root in zip(stores, roots):
                if store.root != root:
                    raise StagingError("protected root configuration changed; HOLD")
                store._checked(root, directory=True)
                for ancestor in (*reversed(root.parents), root):
                    pin(ancestor)
            if (identities[roots[0]][:2] == identities[roots[1]][:2]
                    or self.verify_layout(*roots) is not True):
                raise StagingError("protected C/E layout unverified; HOLD")
            # A verifier must not change a boundary while checking it.
            for path in tuple(identities):
                pin(path)
            if tuple(store.root for store in stores) != roots:
                raise StagingError("protected root configuration changed; HOLD")

        def check_copies(*, complete=False):
            for store, folder in zip(stores, staging):
                # lstat distinguishes absent from inaccessible/dangling objects.
                try:
                    folder.lstat()
                except FileNotFoundError:
                    if folder in identities or complete:
                        raise StagingError("protected staging disappeared; HOLD") from None
                    continue
                store._checked(folder, directory=True)
                pin(folder)
                names = {child.name for child in folder.iterdir()}
                if not names <= set(files) or (complete and names != set(files)):
                    raise StagingError("unexpected or incomplete protected staging; HOLD")
                for name in names:
                    path = folder / name
                    store._checked(path, directory=False)
                    pin(path)
                    actual = store._read_copy(path, len(files[name]) + 1)
                    if (actual != files[name]
                            or observation.digest(actual) != dict(digests)[name]):
                        raise StagingError("protected copy bytes/SHA-256 mismatch; HOLD")
                    store._checked(path, directory=False)
                    pin(path)

        def checkpoint():
            ProtectedEvidenceStore._revalidate(revalidate_input)
            boundaries()
            check_copies()
            if restorer is not None:
                restorer.check()
            ProtectedEvidenceStore._revalidate(revalidate_input)
            boundaries()

        receipt = None
        try:
            with self.exclusive_section():
                boundaries()
                if inventory_store is not None:
                    inventory_store.preflight(event_id)
                if registration_core is not None:
                    registration_core.preflight(stores, restore_store)
                if restorer is not None:
                    restorer.preflight()
                # Check BOTH reservations before creating either one. Never reuse
                # a partial attempt or invent another evidence identifier.
                for folder in staging:
                    try:
                        folder.lstat()
                    except FileNotFoundError:
                        continue
                    raise StagingError("protected staging collision; HOLD")
                checkpoint()
                for store, expected_dir in zip(stores, staging):
                    staged = store.stage(evidence, pending_bytes, revalidate_input=checkpoint)
                    if staged.staging_dir != expected_dir or staged.state != "HOLD":
                        raise StagingError("unexpected staging receipt; HOLD")
                    checkpoint()
                check_copies(complete=True)
                checkpoint()
                if restorer is not None:
                    restored = restorer.run(stores, staging, checkpoint)
                    check_copies(complete=True)
                    checkpoint()
                    receipt = RestoredStagedReview(*staging, digests, restored)
                    if inventory_store is not None:
                        inventory_store.record(evidence, pending_bytes, (*staging, restored), checkpoint)
                        checkpoint()
                        inventory_store.verify_record()
                    if registration_core is not None:
                        receipt = registration_core.finish(stores, staging, restore_store, checkpoint, receipt)
                else:
                    receipt = MirroredStagedReview(*staging, digests)
            # A lock-release error prevents even a HOLD receipt being returned.
            if receipt is None:
                raise StagingError("protected exclusive section incomplete; HOLD")
            return receipt
        except StagingError:
            raise
        except (OSError, ValueError):
            # Do not expose private paths, SID/SDDL or adapter exception text.
            raise StagingError("protected C/E staging failed; remnants remain HOLD") from None


def _write_exclusive(path: Path, raw: bytes) -> None:
    with path.open("xb") as file:
        if file.write(raw) != len(raw):
            raise OSError("short staging write")
        file.flush()
        os.fsync(file.fileno())
