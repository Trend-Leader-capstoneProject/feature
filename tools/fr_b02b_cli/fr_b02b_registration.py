"""Frozen registration bytes and internal C/E completion, never a CLI success.

Generic I/O is exercised only in isolated stores. Native final registration
requires a separate final-object inventory and protected creation authority. The
existing HOLD inventory is never accepted as completion evidence. History is
verified afresh inside the caller's Gate; no cleanup, recovery or
operating defaults are supplied.
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
REVOKE_KEYS = frozenset("""schema event_id registration_id registration_sha256 revoker_sid
revoked_at_utc reason publish_authorization""".split())


def validate_revocation(raw, manifest, registration_sha256):
    """Validate exact frozen bytes and their binding to a COMPLETE ACCEPTED event."""
    from fr_b02b_reviewer_allowlist import _valid_sid

    try:
        value = _parse(raw, REVOKE_KEYS)
        event_id = value["event_id"]
        if (not re.fullmatch(r"REV-OBS-[0-9a-f]{32}", event_id)
                or UUID(event_id.removeprefix("REV-OBS-")).version != 4
                or value["schema"] != "FR_B02B_REVOKE_V1"
                or value["registration_id"] != manifest["registration_id"]
                or value["registration_sha256"] != registration_sha256
                or manifest["review_result"] != "ACCEPTED"
                or value["publish_authorization"] != "NONE"
                or not _valid_sid(value["revoker_sid"])
                or not observation._timestamp(manifest["registration_recorded_at_utc"])
                <= observation._timestamp(value["revoked_at_utc"]) <= _now()):
            raise ValueError("invalid revocation binding/clock")
        return value
    except (ValueError, OSError, OverflowError):
        raise StagingError("revocation verification blocked; HOLD") from None


@dataclass(frozen=True)
class CurrentReviewState:
    registration_id: str
    effective_review_state: str
    status: str = field(default="PASS_PROTECTED_LOCAL_INTEGRITY_ONLY", init=False)
    publish_authorization: str = field(default="NONE", init=False)
    external_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class InternalRevocation:
    registration_id: str
    event_id: str
    status: str = field(default="REVOKED_LOCAL_REGISTRATION", init=False)
    publish_authorization: str = field(default="NONE", init=False)
    external_eligible: bool = field(default=False, init=False)


def _history_operation(mirror, registration_id, *, allowlist_source, reason=None):
    """Internal Core: hold the same Gate across auth, history, writes and verdict."""
    from fr_b02b_review_service import require_process_sid
    from fr_b02b_reviewer_allowlist import require_authorized_sid

    try:
        _id(registration_id)
        stores = (mirror.primary, mirror.backup)
        if (any(not isinstance(s, ProtectedEvidenceStore) for s in stores)
                or not callable(mirror.verify_layout) or not callable(mirror.exclusive_section)):
            raise StagingError("Core history environment unavailable; HOLD")
        provider = _native_provider(stores)
        final = _final_inventory(provider)
        if provider is not None and (final is None or mirror.verify_layout != provider.verify_layout
                                    or mirror.exclusive_section != provider.exclusive_section):
            raise StagingError("Native final history/Gate binding unavailable; HOLD")
        if final is not None and reason is not None:
            final.ensure_creation_available()
        roots = tuple(s.root for s in stores)
        layout, gate = mirror.verify_layout, mirror.exclusive_section
        sid = None
        last_clock = None

        def environment():
            nonlocal sid, last_clock
            if (stores != (mirror.primary, mirror.backup) or tuple(s.root for s in stores) != roots
                    or mirror.verify_layout != layout or mirror.exclusive_section != gate
                    or _native_provider(stores) is not provider
                    or (provider is not None and provider.final_inventory is not final)
                    or layout(*roots) is not True):
                raise StagingError("history protection/layout changed; HOLD")
            current = require_authorized_sid(require_process_sid(), allowlist_source)
            if sid is not None and current != sid:
                raise StagingError("revoker identity changed; HOLD")
            sid = current
            clock = _now()
            if last_clock is not None and clock < last_clock:
                raise StagingError("history operation clock regressed; HOLD")
            last_clock = clock

        with gate():
            environment()
            history = RegistrationHistory(stores, revalidate_input=environment)
            if registration_id not in history.manifests:
                raise StagingError("registration not found; HOLD")
            manifest = history.manifests[registration_id]
            events = history.revocations[registration_id]
            if reason is None:
                history.check()
                state = "REVOKED" if events else manifest["review_result"]
                result = CurrentReviewState(registration_id, state)
            else:
                if not isinstance(reason, str) or not reason.strip():
                    raise StagingError("revocation reason required; HOLD")
                if manifest["review_result"] != "ACCEPTED":
                    raise StagingError("only ACCEPTED registrations can be revoked; HOLD")
                if events:
                    # Multiple valid historical events are ordered by time then ID;
                    # repeated requests never allocate or append another event.
                    event = max((validate_revocation(raw, manifest,
                        history.completions[registration_id].registration_sha256) for raw in events.values()),
                        key=lambda value: (observation._timestamp(value["revoked_at_utc"]), value["event_id"]))
                else:
                    event = dict(schema="FR_B02B_REVOKE_V1", event_id="REV-OBS-" + uuid4().hex,
                        registration_id=registration_id,
                        registration_sha256=history.completions[registration_id].registration_sha256,
                        revoker_sid=sid, revoked_at_utc=_now().isoformat().replace("+00:00", "Z"),
                        reason=reason.strip(), publish_authorization="NONE")
                    raw = observation.canonical_bytes(event)
                    validate_revocation(raw, manifest, event["registration_sha256"])
                    for store in stores:
                        history.check()
                        validate_revocation(raw, manifest, event["registration_sha256"])
                        folder = store.root / "registrations" / registration_id
                        directory = folder / "revocations"
                        store._create_staging(directory)  # Exclusive; never adopt residue.
                        store._checked(directory, directory=True)
                        history._pin(directory)
                        history.names[folder] = history.names[folder] | {"revocations"}
                        history.names[directory] = frozenset()
                        history.check()
                        path = directory / (event["event_id"] + ".json")
                        store._write_file(path, raw)
                        store._checked(path, directory=False)
                        history._pin(path)
                        history.saved[path] = (store, raw)
                        history.names[directory] = frozenset({path.name})
                        history.check()
                    if final is not None:
                        paths = [path for store in stores
                                 for path in (store.root / "registrations" / registration_id / "revocations",
                                     store.root / "registrations" / registration_id / "revocations" / (event["event_id"] + ".json"))]
                        final.record("REVOCATION", registration_id, event["event_id"], paths)
                    # New independent scan validates C/E event sets/bytes/links.
                    verified = RegistrationHistory(stores, revalidate_input=environment)
                    if verified.revocations[registration_id] != {event["event_id"] + ".json": raw}:
                        raise StagingError("revocation final mismatch; HOLD")
                    verified.check()
                history.check()
                result = InternalRevocation(registration_id, event["event_id"])
        return result  # Gate release failure suppresses success.
    except (ValueError, OSError, TypeError, OverflowError):
        raise StagingError("protected history operation blocked; HOLD") from None


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"REG-OBS-[0-9a-f]{32}", value):
        raise StagingError("invalid registration identifier; HOLD")
    parsed = UUID(value.removeprefix("REG-OBS-"))
    if parsed.version != 4:
        raise StagingError("registration identifier is not UUID4; HOLD")
    return value


def _native_provider(stores):
    providers = [store._native_boundary for store in stores]
    if not any(provider is not None for provider in providers):
        return None
    provider = providers[0]
    if provider is None or any(item is not provider for item in providers):
        raise StagingError("mixed Native final-object boundaries; HOLD")
    if tuple(store.root for store in stores) != (provider.policy.primary, provider.policy.backup):
        raise StagingError("Native final copy roots changed; HOLD")
    return provider


def _names(store, folder):
    provider = store._native_boundary
    if provider is not None:
        store._checked(folder, directory=True)
        return _final_inventory(provider)._names(folder)
    return frozenset(path.name for path in folder.iterdir())


def _final_inventory(provider):
    if provider is None:
        return None
    from fr_b02b_inventory import FinalObjectInventory
    final = provider.final_inventory
    if not isinstance(final, FinalObjectInventory) or final.boundary is not provider:
        raise StagingError("Native final inventory/Gate binding unavailable; HOLD")
    return final


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


def build_manifest(evidence, pending_bytes, *, supersedes_registration_id=None):
    """All source/decision fields are derived; only a provisional UUID is allocated."""
    try:
        value = _base(evidence, pending_bytes)
        value.update(registration_id="REG-OBS-" + uuid4().hex,
                     registration_recorded_at_utc=_now().isoformat().replace("+00:00", "Z"),
                     supersedes_registration_id=supersedes_registration_id)
        raw = observation.canonical_bytes(value)
        validate_manifest(raw, evidence, pending_bytes)
        return raw
    except (ValueError, OSError, OverflowError):
        raise StagingError("registration manifest construction blocked; HOLD") from None


def _validate_manifest_bindings(raw, evidence, pending_bytes):
    """Internal byte/link/order checks without reading the current clock.

    Does not verify current registration validity, C/E copies or revocations.
    Operational callers must continue to use validate_manifest/history checks.
    """
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
        if not created <= reviewed <= recorded:
            raise ValueError("registration clock order")
        return value
    except (ValueError, OSError, OverflowError):
        raise StagingError("registration manifest fields/links/clock invalid; HOLD") from None


def validate_manifest(raw, evidence, pending_bytes):
    value = _validate_manifest_bindings(raw, evidence, pending_bytes)
    try:
        if observation._timestamp(value["registration_recorded_at_utc"]) > _now():
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


@dataclass(frozen=True, repr=False)
class InternalHistoryReview:
    """No invented staging/restore receipt when reusing an existing history."""
    completion: InternalCompletion
    state: str = field(default="HOLD", init=False)
    publish_authorization: str = field(default="NONE", init=False)


def verify_registration_copies(stores, folders, evidence, pending_bytes, *, revalidate_input):
    completion, data = _verify_registration_copies(
        stores, folders, evidence, pending_bytes, revalidate_input=revalidate_input)
    if data["supersedes_registration_id"] is not None:
        raise StagingError("registration history must be verified as a whole; HOLD")
    return completion


def _verify_registration_copies(stores, folders, evidence, pending_bytes, *, revalidate_input,
                                allow_revocations=False):
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
        def file_set(store, folder):
            names = _names(store, folder)
            if names != REGISTRATION_FILES and not (allow_revocations and names == REGISTRATION_FILES | {"revocations"}):
                raise ValueError("incomplete/unexpected registration set")
            return names

        copies = []
        namespaces = []
        for store, folder in zip(stores, folders):
            revalidate_input()
            store._checked(folder, directory=True)
            pin(folder)
            names = file_set(store, folder)
            namespaces.append(names)
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
            if file_set(store, folder) != names:
                raise ValueError("registration set changed")
        if copies[0] != copies[1]:
            raise ValueError("two-copy disagreement")
        for store, folder, saved, names in zip(stores, folders, copies, namespaces):
            revalidate_input()
            store._checked(store.root, directory=True)
            store._checked(folder, directory=True)
            if file_set(store, folder) != names:
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
        return InternalCompletion(data["registration_id"], observation.digest(copies[0]["registration.json"])), data
    except (ValueError, OSError):
        raise StagingError("registration completion verification blocked; HOLD") from None


def _stored_review(files):
    """Rebuild old decision metadata, never substitute the current decision."""
    from fr_b02b_a1_adapter import _load_a1_snapshot_bytes

    value = _parse(files["registration.json"], KEYS)
    snapshot = _load_a1_snapshot_bytes(files["a1_archive.zip"])
    record = observation._validate_records(snapshot, files["observation.json"], files["index.json"],
                                           value["local_evidence_id"])
    evidence = observation.VerifiedObservation(snapshot, record, files["observation.json"], files["index.json"])
    from fr_b02b_protected_store import PENDING_KEYS
    pending = observation.canonical_bytes({key: value[key] for key in PENDING_KEYS})
    validate_manifest(files["registration.json"], evidence, pending)
    return evidence, pending


class RegistrationHistory:
    """Ephemeral verified snapshot, NOT a persisted Native trust inventory.

    Generic I/O is for isolated Core stores only. Native trust is loaded from
    separate protected records before any discovered history is consumed.
    """
    def __init__(self, stores, *, revalidate_input):
        if (len(stores) != 2 or any(not isinstance(store, ProtectedEvidenceStore)
                or not isinstance(store.root, Path)
                or not store.root.is_absolute() for store in stores)
                or stores[0].root.is_relative_to(stores[1].root)
                or stores[1].root.is_relative_to(stores[0].root)
                or not callable(revalidate_input)):
            raise StagingError("final-registration history environment unavailable; HOLD")
        self.stores, self.revalidate_input = stores, revalidate_input
        self.roots = tuple(store.root for store in stores)
        self.names, self.saved, self.identities = {}, {}, {}
        self.manifests, self.completions = {}, {}
        self.revocations = {}
        provider = _native_provider(stores)
        self.final_inventory = _final_inventory(provider)
        if provider is not None and self.final_inventory is None:
            raise StagingError("Native final-object inventory unavailable; HOLD")
        try:
            if self.final_inventory is not None:
                self.final_inventory.verify_existing()
            names = []
            for store in stores:
                store._checked(store.root, directory=True)
                self._pin(store.root)
                container = store._checked(store.root / "registrations", directory=True)
                self._pin(container)
                current = _names(store, container)
                if len(current) > 1024:
                    raise ValueError("history size limit")
                for rid in current:
                    _id(rid)
                self.names[container] = current
                names.append(current)
            if self.identities[stores[0].root][:2] == self.identities[stores[1].root][:2]:
                raise ValueError("same physical copy root")
            if names[0] != names[1]:
                raise ValueError("one-sided history")
            for rid in sorted(names[0]):
                folders = tuple(store.root / "registrations" / rid for store in stores)
                copies = []
                for store, folder in zip(stores, folders):
                    store._checked(folder, directory=True)
                    self._pin(folder)
                    members = _names(store, folder)
                    if members not in (REGISTRATION_FILES, REGISTRATION_FILES | {"revocations"}):
                        raise ValueError("incomplete/unexpected registration or revocation")
                    self.names[folder] = members
                    files = {}
                    for name in sorted(REGISTRATION_FILES):
                        self.revalidate_input()
                        path = store._checked(folder / name, directory=False)
                        self._pin(path)
                        limit = 20 * 1024 * 1024 if name == "a1_archive.zip" else observation.MAX_RECORD_BYTES
                        raw = store._read_copy(path, limit + 1)
                        if not isinstance(raw, bytes) or len(raw) > limit:
                            raise ValueError("history file size")
                        files[name] = raw
                        self.saved[path] = (store, raw)
                    copies.append(files)
                if copies[0] != copies[1]:
                    raise ValueError("history copies disagree")
                evidence, pending = _stored_review(copies[0])
                completion, data = _verify_registration_copies(
                    stores, folders, evidence, pending, revalidate_input=self.revalidate_input,
                    allow_revocations=True)
                self.manifests[rid], self.completions[rid] = data, completion
                events = []
                for store, folder in zip(stores, folders):
                    current = {}
                    if "revocations" in self.names[folder]:
                        directory = store._checked(folder / "revocations", directory=True)
                        self._pin(directory)
                        names = _names(store, directory)
                        if not names or len(names) > 1024:
                            raise ValueError("empty/oversized revocations")
                        self.names[directory] = names
                        for name in sorted(names):
                            self.revalidate_input()
                            path = store._checked(directory / name, directory=False)
                            self._pin(path)
                            raw = store._read_copy(path, observation.MAX_RECORD_BYTES + 1)
                            event = validate_revocation(raw, data, completion.registration_sha256)
                            if name != event["event_id"] + ".json":
                                raise ValueError("revocation filename mismatch")
                            current[name] = raw
                            self.saved[path] = (store, raw)
                    events.append(current)
                if events[0] != events[1]:
                    raise ValueError("revocation copies disagree")
                self.revocations[rid] = events[0]
            from fr_b02b_inventory import registration_history_tip
            self.tips = {}
            for event in {row["local_evidence_id"] for row in self.manifests.values()}:
                self.tips[event] = registration_history_tip(
                    [row for row in self.manifests.values() if row["local_evidence_id"] == event], event)
            self.check()
        except (ValueError, OSError, KeyError):
            raise StagingError("registration history verification blocked; HOLD") from None

    def _pin(self, path):
        info = path.lstat()
        identity = info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)
        if stat.S_ISREG(info.st_mode):
            identity += (info.st_size, info.st_mtime_ns)
        if not info.st_ino or identity != self.identities.setdefault(path, identity):
            raise StagingError("registration history identity changed; HOLD")

    def check(self, additional=()):
        self.revalidate_input()
        if self.final_inventory is not None:
            if _final_inventory(_native_provider(self.stores)) is not self.final_inventory:
                raise StagingError("Native final inventory binding changed; HOLD")
            self.final_inventory.check()
        if tuple(store.root for store in self.stores) != self.roots:
            raise StagingError("registration history roots changed; HOLD")
        for store in self.stores:
            store._checked(store.root, directory=True)
            container = store._checked(store.root / "registrations", directory=True)
            extra = {path.name for path in additional if path.parent == container}
            if _names(store, container) != self.names[container] | extra:
                raise StagingError("registration history namespace changed; HOLD")
            for path, names in self.names.items():
                if path != container and path.is_relative_to(container):
                    store._checked(path, directory=True)
                    if _names(store, path) != names:
                        raise StagingError("registration history file set changed; HOLD")
        for path, (store, raw) in self.saved.items():
            store._checked(path, directory=False)
            self._pin(path)
            if store._read_copy(path, len(raw) + 1) != raw:
                raise StagingError("registration history bytes changed; HOLD")
        for path in self.identities:
            self._pin(path)
        self.revalidate_input()

    def tip_for(self, evidence, pending_bytes):
        current = _base(evidence, pending_bytes)
        tip = self.tips.get(current["local_evidence_id"])
        if tip is not None:
            row = self.manifests[tip]
            if self.revocations[tip]:
                raise StagingError("revoked observation cannot be registered again; HOLD")
            decision_keys = {"reviewer_sid", "reviewed_at_utc", "review_result", "decision_reason"}
            if any(row[key] != value for key, value in current.items() if key not in decision_keys):
                raise StagingError("observation already bound to different evidence; HOLD")
        return tip


class RegistrationCore:
    def __init__(self, manifest, evidence, pending_bytes):
        value = validate_manifest(manifest, evidence, pending_bytes) if manifest is not None else None
        if value is not None and value["supersedes_registration_id"] is not None:
            raise StagingError("supersession history validation not configured; HOLD")
        self.manifest, self.evidence, self.pending_bytes = manifest, evidence, pending_bytes
        self.registration_id = value["registration_id"] if value is not None else None
        self.files = {key: raw for key, raw in _validated_files(evidence, pending_bytes).items() if key in SOURCE_FILES}
        self.files["registration.json"] = manifest
        self.identities = {}
        self.written = {}
        self.history = None

    def require_environment(self, stores, restore_store, evidence, pending_bytes):
        if evidence != self.evidence or pending_bytes != self.pending_bytes:
            raise StagingError("registration plan does not match current review; HOLD")
        if restore_store is None:
            raise StagingError("Native final-registration inventory/protection not configured; HOLD")
        provider = _native_provider(stores)
        self.final_inventory = _final_inventory(provider)
        if provider is not None:
            if restore_store._native_boundary is not provider or self.final_inventory is None:
                raise StagingError("Native final inventory/restore boundary unavailable; HOLD")
            self.final_inventory.ensure_creation_available()
        elif restore_store._native_boundary is not None:
            raise StagingError("mixed final restore boundary; HOLD")

    def _pin(self, path):
        stat_result = path.lstat()
        identity = stat_result.st_dev, stat_result.st_ino, stat.S_IFMT(stat_result.st_mode)
        if not stat_result.st_ino or identity != self.identities.setdefault(path, identity):
            raise StagingError("registration object identity changed; HOLD")

    def preflight(self, stores, restore_store, *, revalidate_input):
        self.stores, self.restore_store = stores, restore_store
        self.history = RegistrationHistory(stores, revalidate_input=revalidate_input)
        tip = self.history.tip_for(self.evidence, self.pending_bytes)
        if tip is not None and self.history.manifests[tip]["review_result"] == "ACCEPTED":
            self.history.check()
            return InternalHistoryReview(self.history.completions[tip])
        if tip is not None:
            reviewed = observation._timestamp(json.loads(self.pending_bytes)["reviewed_at_utc"])
            if reviewed < observation._timestamp(self.history.manifests[tip]["registration_recorded_at_utc"]):
                raise StagingError("review clock predates prior registration; HOLD")
        if self.manifest is None:
            self.manifest = build_manifest(self.evidence, self.pending_bytes, supersedes_registration_id=tip)
            self.registration_id = json.loads(self.manifest)["registration_id"]
            self.files["registration.json"] = self.manifest
        elif tip is not None:
            raise StagingError("preallocated plan cannot supersede existing history; HOLD")
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
            if self.registration_id in self.history.names[container]:
                raise StagingError("registration identifier collision; HOLD")
        try:
            self.restore_folder.lstat()
        except FileNotFoundError:
            pass
        else:
            raise StagingError("registration restore target collision; HOLD")
        if tip is not None:
            # Previous COMPLETE sources have already passed C/E validation. Do
            # not reuse or overwrite their old pending-decision staging files.
            sources = tuple(store.root / "registrations" / tip for store in stores)
            return self.finish(stores, sources, restore_store, revalidate_input, None)
        return None

    def _check(self, checkpoint):
        checkpoint()  # Original bytes, SID, Allowlist, HOLD copies/restore and Gate.
        validate_manifest(self.manifest, self.evidence, self.pending_bytes)
        if tuple(store.root for store in (*self.stores, self.restore_store)) != self.roots:
            raise StagingError("registration root configuration changed; HOLD")
        for store in (*self.stores, self.restore_store):
            store._checked(store.root, directory=True)
        for path in tuple(self.identities):
            self._pin(path)
        if self.history is not None:
            self.history.check({folder for folder in self.written if folder in self.folders})
        for folder, (store, names) in self.written.items():
            store._checked(folder, directory=True)
            if _names(store, folder) != names:
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
        if self.final_inventory is not None:
            paths = [path for folder, (_, names) in self.written.items()
                     for path in (folder, *(folder / name for name in names))]
            self.final_inventory.record("REGISTRATION", self.registration_id, self.registration_id, paths)
            # Full trusted C/E history re-scan after the append-only seal.
            RegistrationHistory(stores, revalidate_input=checkpoint).check()
        if staged_receipt is None:
            return InternalHistoryReview(completion)
        return CompletedStagedReview(staged_receipt.primary_staging_dir, staged_receipt.backup_staging_dir,
                                      staged_receipt.sha256, staged_receipt.restored_staging_dir, completion)

    def verify_completed(self, checkpoint):
        self._check(checkpoint)
        completion, data = _verify_registration_copies(
            self.stores, self.folders, self.evidence, self.pending_bytes,
            revalidate_input=lambda: self._check(checkpoint))
        from fr_b02b_inventory import registration_history_tip
        rows = [row for row in self.history.manifests.values()
                if row["local_evidence_id"] == data["local_evidence_id"]] if self.history is not None else []
        if registration_history_tip([*rows, data], data["local_evidence_id"]) != self.registration_id:
            raise StagingError("new registration is not the unique history tip; HOLD")
        self._check(checkpoint)
        return completion
