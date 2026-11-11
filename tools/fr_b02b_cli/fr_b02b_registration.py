"""Frozen registration bytes and internal C/E completion, never a CLI success.

Generic I/O is exercised only in isolated stores. Native final registration is
blocked until its final-object inventory/protected creation is implemented. The
existing HOLD inventory is never accepted as completion evidence. No history,
revocation, restart acceptance, cleanup, recovery or operating defaults.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

import fr_b02b_observation as observation
from fr_b02b_protected_store import ProtectedEvidenceStore, RestoredStagedReview, StagingError, _validated_files

SCHEMA = "FR_B02B_PROTECTED_REVIEW_V1"
COMPLETE_SCHEMA = "FR_B02B_REGISTRATION_COMPLETE_V1"
SOURCE_FILES = frozenset({"a1_archive.zip", "observation.json", "index.json"})
BASE_FILES = SOURCE_FILES | {"registration.json"}
REGISTRATION_FILES = BASE_FILES | {"registration_complete.json"}
KEYS = frozenset("""schema registration_id local_evidence_id a1_archive_sha256 observation_sha256
index_sha256 trend_ref content_ref review_evidence_id source_url event_kind observation_method
confirmed_at_utc record_created_at_utc observer_ref actor_assurance reviewer_sid reviewed_at_utc
review_result decision_reason registration_recorded_at_utc supersedes_registration_id publish_authorization""".split())


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"REG-OBS-[0-9a-f]{32}", value):
        raise StagingError("invalid registration identifier; HOLD")
    parsed = UUID(value.removeprefix("REG-OBS-"))
    if parsed.version != 4:
        raise StagingError("registration identifier is not UUID4; HOLD")
    return value


def _now():
    value = observation.utc_now()
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise StagingError("registration UTC clock unavailable; HOLD")
    return value.astimezone(timezone.utc)


def _parse(raw, keys):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= observation.MAX_RECORD_BYTES:
            raise ValueError("invalid JSON byte size")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        if not isinstance(value, dict) or set(value) != keys or observation.canonical_bytes(value) != raw:
            raise ValueError("invalid canonical fields")
        for key, item in value.items():
            if key == "supersedes_registration_id" and item is None:
                continue
            if not isinstance(item, str) or (key != "decision_reason" and not item.strip()):
                raise ValueError("invalid string field")
        return value
    except (ValueError, TypeError, RecursionError):
        raise StagingError("invalid canonical registration JSON; HOLD") from None


def _base(evidence, pending_bytes):
    files = _validated_files(evidence, pending_bytes)
    pending = json.loads(pending_bytes)
    record = evidence.record
    value = {name: record[name] for name in (
        "trend_ref", "content_ref", "review_evidence_id", "source_url", "event_kind",
        "observation_method", "confirmed_at_utc", "record_created_at_utc", "observer_ref", "actor_assurance")}
    value.update({name: pending[name] for name in (
        "local_evidence_id", "reviewer_sid", "reviewed_at_utc", "review_result", "decision_reason")})
    value.update(schema=SCHEMA, publish_authorization="NONE")
    for name, filename in (("a1_archive_sha256", "a1_archive.zip"),
                           ("observation_sha256", "observation.json"), ("index_sha256", "index.json")):
        value[name] = observation.digest(files[filename])
    return value


def build_manifest(evidence, pending_bytes):
    """All source/decision fields are derived; only a provisional UUID is allocated."""
    try:
        value = _base(evidence, pending_bytes)
        value.update(registration_id="REG-OBS-" + uuid4().hex,
                     registration_recorded_at_utc=_now().isoformat().replace("+00:00", "Z"),
                     supersedes_registration_id=None)
        raw = observation.canonical_bytes(value)
        validate_manifest(raw, evidence, pending_bytes)
        return raw
    except (ValueError, OSError, OverflowError):
        raise StagingError("registration manifest construction blocked; HOLD") from None


def validate_manifest(raw, evidence, pending_bytes):
    try:
        value = _parse(raw, KEYS)
        _id(value["registration_id"])
        parent = value["supersedes_registration_id"]
        if parent is not None:
            _id(parent)
            if parent == value["registration_id"]:
                raise ValueError("self supersession")
        if any(value[key] != expected for key, expected in _base(evidence, pending_bytes).items()):
            raise ValueError("review/source mismatch")
        if not re.fullmatch(r"S-1-(?:\d+-)+\d+", value["reviewer_sid"]):
            raise ValueError("invalid process SID")
        created = observation._timestamp(value["record_created_at_utc"])
        reviewed = observation._timestamp(value["reviewed_at_utc"])
        recorded = observation._timestamp(value["registration_recorded_at_utc"])
        if not created <= reviewed <= recorded <= _now():
            raise ValueError("registration clock order")
        return value
    except (ValueError, OSError, OverflowError):
        raise StagingError("registration manifest fields/links/clock invalid; HOLD") from None


def build_complete_marker(manifest, evidence, pending_bytes):
    value = validate_manifest(manifest, evidence, pending_bytes)
    return observation.canonical_bytes({"schema": COMPLETE_SCHEMA, "registration_id": value["registration_id"],
                                         "registration_sha256": observation.digest(manifest), "status": "COMPLETE"})


def validate_complete_marker(raw, manifest, evidence, pending_bytes):
    value = _parse(raw, frozenset({"schema", "registration_id", "registration_sha256", "status"}))
    if raw != build_complete_marker(manifest, evidence, pending_bytes):
        raise StagingError("registration completion marker mismatch; HOLD")
    return value


@dataclass(frozen=True, repr=False)
class InternalCompletion:
    registration_id: str
    registration_sha256: str
    copies_complete: bool = field(default=True, init=False)
    external_eligible: bool = field(default=False, init=False)
    publish_authorization: str = field(default="NONE", init=False)


@dataclass(frozen=True, repr=False)
class CompletedStagedReview(RestoredStagedReview):
    completion: InternalCompletion


def verify_registration_copies(stores, folders, evidence, pending_bytes, *, revalidate_input):
    """Caller holds Gate. Copy-integrity only; no history/restart/operating authorization."""
    try:
        identities = {}

        def pin(path):
            info = path.lstat()
            identity = info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)
            if not info.st_ino or identity != identities.setdefault(path, identity):
                raise ValueError("registration verification object changed")

        if len(stores) != 2 or len(folders) != 2:
            raise ValueError("two copies required")
        if any(not isinstance(store, ProtectedEvidenceStore) or not isinstance(store.root, Path)
               or not store.root.is_absolute() for store in stores):
            raise ValueError("unconfigured protected copy roots")
        if stores[0].root.is_relative_to(stores[1].root) or stores[1].root.is_relative_to(stores[0].root):
            raise ValueError("overlapping copy roots")
        root_ids = []
        for store, folder in zip(stores, folders):
            store._checked(store.root, directory=True)
            pin(store.root)
            info = store.root.lstat()
            root_ids.append((info.st_dev, info.st_ino))
            if not isinstance(folder, Path) or folder.parent != store.root / "registrations":
                raise ValueError("invalid registration layout")
            _id(folder.name)
        if root_ids[0] == root_ids[1]:
            raise ValueError("two paths reference one copy root")
        expected = _validated_files(evidence, pending_bytes)
        copies = []
        for store, folder in zip(stores, folders):
            revalidate_input()
            store._checked(folder, directory=True)
            pin(folder)
            if {path.name for path in folder.iterdir()} != REGISTRATION_FILES:
                raise ValueError("incomplete registration set")
            saved = {}
            for name in sorted(REGISTRATION_FILES):
                revalidate_input()
                path = store._checked(folder / name, directory=False)
                pin(path)
                limit = len(expected[name]) + 1 if name in SOURCE_FILES else observation.MAX_RECORD_BYTES + 1
                saved[name] = store._read_copy(path, limit)
                store._checked(path, directory=False)
                pin(path)
                if name in SOURCE_FILES and (saved[name] != expected[name]
                        or observation.digest(saved[name]) != observation.digest(expected[name])):
                    raise ValueError("original copy mismatch")
            manifest = validate_manifest(saved["registration.json"], evidence, pending_bytes)
            if manifest["registration_id"] != folder.name:
                raise ValueError("manifest/directory identity mismatch")
            validate_complete_marker(saved["registration_complete.json"], saved["registration.json"], evidence, pending_bytes)
            copies.append(saved)
            store._checked(folder, directory=True)
            if {path.name for path in folder.iterdir()} != REGISTRATION_FILES:
                raise ValueError("registration set changed")
        if copies[0] != copies[1]:
            raise ValueError("two-copy disagreement")
        for store, folder, saved in zip(stores, folders, copies):
            revalidate_input()
            store._checked(store.root, directory=True)
            store._checked(folder, directory=True)
            if {path.name for path in folder.iterdir()} != REGISTRATION_FILES:
                raise ValueError("registration set changed before verdict")
            for name, raw in saved.items():
                path = store._checked(folder / name, directory=False)
                pin(path)
                if store._read_copy(path, len(raw) + 1) != raw:
                    raise ValueError("registration copy changed before verdict")
                store._checked(path, directory=False)
                pin(path)
        for path in identities:
            pin(path)
        revalidate_input()
        data = validate_manifest(copies[0]["registration.json"], evidence, pending_bytes)
        if data["supersedes_registration_id"] is not None:
            raise ValueError("history not verified")
        return InternalCompletion(data["registration_id"], observation.digest(copies[0]["registration.json"]))
    except (ValueError, OSError):
        raise StagingError("registration completion verification blocked; HOLD") from None


class RegistrationCore:
    def __init__(self, manifest, evidence, pending_bytes):
        value = validate_manifest(manifest, evidence, pending_bytes)
        if value["supersedes_registration_id"] is not None:
            raise StagingError("supersession history validation not configured; HOLD")
        self.manifest, self.evidence, self.pending_bytes = manifest, evidence, pending_bytes
        self.registration_id = value["registration_id"]
        self.files = {key: raw for key, raw in _validated_files(evidence, pending_bytes).items() if key in SOURCE_FILES}
        self.files["registration.json"] = manifest
        self.identities = {}
        self.written = {}

    def require_environment(self, stores, restore_store, evidence, pending_bytes):
        if evidence != self.evidence or pending_bytes != self.pending_bytes:
            raise StagingError("registration plan does not match current review; HOLD")
        if restore_store is None or any(store._native_boundary is not None for store in (*stores, restore_store)):
            # Current protected inventory describes HOLD objects only. It cannot
            # attest a final registration graph, and its Native creator is OFF.
            raise StagingError("Native final-registration inventory/protection not configured; HOLD")

    def _pin(self, path):
        stat_result = path.lstat()
        identity = stat_result.st_dev, stat_result.st_ino, stat.S_IFMT(stat_result.st_mode)
        if not stat_result.st_ino or identity != self.identities.setdefault(path, identity):
            raise StagingError("registration object identity changed; HOLD")

    def preflight(self, stores, restore_store):
        self.stores, self.restore_store = stores, restore_store
        self.folders = tuple(store.root / "registrations" / self.registration_id for store in stores)
        self.restore_folder = restore_store.root / (".review-registration-restore-" + self.registration_id)
        self.roots = tuple(store.root for store in (*stores, restore_store))
        for store in (*stores, restore_store):
            store._checked(store.root, directory=True)
            for path in (*reversed(store.root.parents), store.root):
                self._pin(path)
        for store, folder in zip(stores, self.folders):
            container = store._checked(folder.parent, directory=True)  # Pre-managed; never auto-created.
            self._pin(container)
            if any(container.iterdir()):
                raise StagingError("registration collision/history requires separate validation; HOLD")
        try:
            self.restore_folder.lstat()
        except FileNotFoundError:
            return
        raise StagingError("registration restore target collision; HOLD")

    def _check(self, checkpoint):
        checkpoint()  # Original bytes, SID, Allowlist, HOLD copies/restore and Gate.
        validate_manifest(self.manifest, self.evidence, self.pending_bytes)
        if tuple(store.root for store in (*self.stores, self.restore_store)) != self.roots:
            raise StagingError("registration root configuration changed; HOLD")
        for store in (*self.stores, self.restore_store):
            store._checked(store.root, directory=True)
        for path in tuple(self.identities):
            self._pin(path)
        for folder, (store, names) in self.written.items():
            store._checked(folder, directory=True)
            if {path.name for path in folder.iterdir()} != names:
                raise StagingError("partial/unexpected registration file set; HOLD")
            for name in names:
                path = store._checked(folder / name, directory=False)
                self._pin(path)
                expected = self.marker if name == "registration_complete.json" else self.files[name]
                raw = store._read_copy(path, len(expected) + 1)
                if raw != expected or observation.digest(raw) != observation.digest(expected):
                    raise StagingError("registration copy bytes/hash mismatch; HOLD")
                store._checked(path, directory=False)
                self._pin(path)

    def _new_folder(self, store, folder):
        store._create_staging(folder)
        store._checked(folder, directory=True)
        self._pin(folder)
        self.written[folder] = (store, set())

    def _write(self, store, folder, name, raw):
        store._write_file(folder / name, raw)
        self.written[folder][1].add(name)
        store._checked(folder / name, directory=False)
        self._pin(folder / name)

    def finish(self, stores, staging, restore_store, checkpoint, staged_receipt):
        self._check(checkpoint)
        # Copy originals from the protected BACKUP, not from mutable input paths.
        backup = {name: stores[1]._read_copy(staging[1] / name, len(self.files[name]) + 1) for name in SOURCE_FILES}
        if any(raw != self.files[name] for name, raw in backup.items()):
            raise StagingError("registration backup source mismatch; HOLD")
        for store, folder in zip(stores, self.folders):
            self._check(checkpoint)
            self._new_folder(store, folder)
            for name in sorted(BASE_FILES):
                self._check(checkpoint)
                self._write(store, folder, name, self.manifest if name == "registration.json" else backup[name])
            self._check(checkpoint)
        # Reuse the restoration boundary and verify a NEW manifest-inclusive
        # backup round trip before writing EITHER completion marker.
        self._new_folder(restore_store, self.restore_folder)
        for name in sorted(BASE_FILES):
            self._check(checkpoint)
            raw = stores[1]._read_copy(self.folders[1] / name, len(self.files[name]) + 1)
            if raw != self.files[name]:
                raise StagingError("registration restore source changed; HOLD")
            self._write(restore_store, self.restore_folder, name, raw)
        self._check(checkpoint)
        validate_manifest(restore_store._read_copy(self.restore_folder / "registration.json", len(self.manifest) + 1),
                          self.evidence, self.pending_bytes)
        self.marker = build_complete_marker(self.manifest, self.evidence, self.pending_bytes)
        for store, folder in zip(stores, self.folders):
            self._check(checkpoint)
            self._write(store, folder, "registration_complete.json", self.marker)
            self._check(checkpoint)
        completion = self.verify_completed(checkpoint)
        return CompletedStagedReview(staged_receipt.primary_staging_dir, staged_receipt.backup_staging_dir,
                                      staged_receipt.sha256, staged_receipt.restored_staging_dir, completion)

    def verify_completed(self, checkpoint):
        self._check(checkpoint)
        completion = verify_registration_copies(
            self.stores, self.folders, self.evidence, self.pending_bytes,
            revalidate_input=lambda: self._check(checkpoint))
        self._check(checkpoint)
        return completion
