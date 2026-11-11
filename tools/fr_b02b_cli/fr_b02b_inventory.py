"""Separate protected trust inventory, never a registration manifest.

Native creation is BLOCKED without a separately approved protected-creation
authority. A reviewer-owned/writeable file is not a seal. Tests model such an
authority; the current Win32 adapter deliberately provides none. Administrator
compromise is not excluded. No ACL setter, self-approval, discovery-based repair,
retry, cleanup, signing service or operating path is supplied here.
"""

from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass
import json
from pathlib import Path
import re

import fr_b02b_observation as observation
from fr_b02b_native_store import AclPolicy, ApprovedObject, NativeStoreBoundary, _policy_valid
from fr_b02b_protected_store import StagingError, _validated_files
from fr_b02b_restart import FILES, RestartAssessment, _ReadView, _inventory, inspect_restart

MAX_BYTES = 256 * 1024
SCHEMA = "PHASE4B2_TRUST_INVENTORY_V1"
ADMINS = frozenset({"S-1-5-32-544", "S-1-5-18"})


def _inventory_filename(name):
    # Shared namespace only. Each format keeps its own validator; recognizing a
    # final filename does not make a HOLD record attest registration objects.
    return isinstance(name, str) and re.fullmatch(
        r"(?:inventory-LOCAL-OBS-[0-9a-f]{32}|final-(?:REG|REV)-OBS-[0-9a-f]{32})\.json", name)


def registration_history_tip(manifests, event):
    """Check a graph of ALREADY verified manifests; this creates no trust seal.

    The HOLD Native inventory format below remains unchanged and cannot attest
    final registrations. Callers must verify both protected copies first.
    """
    from fr_b02b_registration import KEYS, _id

    try:
        event = _event(event)
        rows = {}
        source_keys = KEYS - {"registration_id", "supersedes_registration_id", "reviewer_sid",
                              "reviewed_at_utc", "registration_recorded_at_utc",
                              "review_result", "decision_reason"}
        fingerprint = None
        for row in manifests:
            if not isinstance(row, dict) or set(row) != KEYS or row["local_evidence_id"] != event:
                raise ValueError("invalid history member")
            rid = _id(row["registration_id"])
            if rid in rows or row["review_result"] not in ("ACCEPTED", "HOLD", "REJECTED"):
                raise ValueError("duplicate/invalid history member")
            current = tuple(row[key] for key in sorted(source_keys))
            if fingerprint is not None and current != fingerprint:
                raise ValueError("conflicting evidence for observation")
            fingerprint = current
            rows[rid] = row
        if not rows:
            return None
        children, roots = {}, []
        for rid, row in rows.items():
            parent = row["supersedes_registration_id"]
            if parent is None:
                roots.append(rid)
                continue
            _id(parent)
            if (parent not in rows or parent == rid or parent in children
                    or rows[parent]["review_result"] not in ("HOLD", "REJECTED")
                    or observation._timestamp(row["reviewed_at_utc"])
                    < observation._timestamp(rows[parent]["registration_recorded_at_utc"])):
                raise ValueError("missing/branched/accepted/nonchronological parent")
            children[parent] = rid
        if len(roots) != 1:
            raise ValueError("ambiguous history root")
        seen, tip = set(), roots[0]
        while tip not in seen:
            seen.add(tip)
            if tip not in children:
                break
            tip = children[tip]
        if len(seen) != len(rows) or tip in children:
            raise ValueError("disconnected/cyclic history")
        return tip
    except (ValueError, TypeError, KeyError):
        raise StagingError("registration history conflict; HOLD") from None


@dataclass(frozen=True, repr=False)
class InventoryPolicy:
    root: ApprovedObject
    file_acl: AclPolicy


@dataclass(frozen=True, repr=False)
class VerifiedInventory:
    local_evidence_id: str
    expected_objects: tuple[ApprovedObject, ...]


def _readonly_acl(acl, reviewer, directory):
    if (not isinstance(acl, AclPolicy) or not isinstance(acl.owner, str)
            or acl.owner not in ADMINS or type(acl.control) is not int or acl.control != 0x1004
            or not isinstance(acl.aces, tuple) or not acl.aces):
        raise StagingError("inventory owner/DACL authority missing; HOLD")
    for ace in acl.aces:
        if (not isinstance(ace, tuple) or len(ace) != 4
                or any(type(value) is not int for value in ace[:3]) or ace[0] not in (0, 1)
                or ace[1] != 0 or type(ace[2]) is not int or not 0 < ace[2] <= 0xFFFFFFFF
                or ace[3] not in (*ADMINS, reviewer)):
            raise StagingError("unsupported inventory protection policy; HOLD")
        if ace[0] == 0 and ace[3] not in ADMINS and ace[2] & ~(0x1200A9 if directory else 0x120089):
            raise StagingError("inventory reviewer write/delete/ACL rights prohibited; HOLD")


def validate_inventory_policy(policy, protection):
    _policy_valid(policy)
    if (not isinstance(protection, InventoryPolicy) or not isinstance(protection.root, ApprovedObject)
            or not protection.root.directory or protection.root not in policy.anchors):
        raise StagingError("approved separate inventory anchor missing; HOLD")
    root = protection.root.path
    # Exclude the APPROVED Config files' parents; never guess a Known Folder
    # absolute path or select a Config directory by its last component's name.
    boundaries = (policy.primary, policy.backup, policy.control)
    if (any(root.is_relative_to(path) or path.is_relative_to(root) for path in boundaries)
            or any(not spec.directory and (spec.path.is_relative_to(root)
                    or root.is_relative_to(spec.path.parent)) for spec in policy.anchors)):
        raise StagingError("inventory area overlaps Config/control/C/E; HOLD")
    _readonly_acl(protection.root.acl, policy.reviewer_sid, True)
    _readonly_acl(protection.file_acl, policy.reviewer_sid, False)


def _plain(value):
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _binding(policy, protection):
    # Binding to EXTERNALLY supplied policy, not authentication by a self-hash.
    return observation.digest(observation.canonical_bytes({"store": _plain(policy), "inventory": _plain(protection)}))


def _event(value):
    try:
        return observation._event_id(value)
    except (TypeError, ValueError):
        raise StagingError("invalid inventory observation identity; HOLD") from None


def _path(protection, event):
    return protection.root.path / ("inventory-" + _event(event) + ".json")


def _shape(specs, policy, event):
    known = _inventory(specs, policy)
    staging = {root / (".review-staging-" + event) for root in (policy.primary, policy.backup)}
    restore = {root / (".review-restore-" + event) for root in (policy.primary, policy.backup)}
    directories = {spec.path for spec in specs if spec.directory}
    if (len(specs) != 15 or len(directories) != 3 or not staging <= directories
            or len(directories & restore) != 1):
        raise StagingError("inventory requires complete C/E and one verified restore; HOLD")
    expected = directories | {folder / name for folder in directories for name in FILES}
    if set(known) != expected or any(spec.directory and spec.sha256 is not None for spec in specs):
        raise StagingError("inventory object set mismatch; HOLD")
    hashes = [{name: known[folder / name].sha256 for name in FILES} for folder in sorted(directories)]
    if any(value != hashes[0] for value in hashes[1:]):
        raise StagingError("inventory C/E/restore digests disagree; HOLD")


def encode_inventory(policy, protection, event, specs):
    validate_inventory_policy(policy, protection)
    event = _event(event)
    _shape(specs, policy, event)
    payload = observation.canonical_bytes({
        "schema": SCHEMA, "local_evidence_id": event, "state": "HOLD",
        "publish_authorization": "NONE", "policy_binding": _binding(policy, protection),
        "objects": [_plain(spec) for spec in sorted(specs, key=lambda item: str(item.path))],
    })
    if len(payload) > MAX_BYTES:
        raise StagingError("inventory size limit exceeded; HOLD")
    return payload


def decode_inventory(raw, policy, protection, event):
    validate_inventory_policy(policy, protection)
    event = _event(event)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
            raise ValueError("invalid inventory size")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(data, dict) or set(data) != {
                "schema", "local_evidence_id", "state", "publish_authorization", "policy_binding", "objects"}
                or data["schema"] != SCHEMA or data["local_evidence_id"] != event
                or data["state"] != "HOLD" or data["publish_authorization"] != "NONE"
                or data["policy_binding"] != _binding(policy, protection)
                or not isinstance(data["objects"], list) or len(data["objects"]) != 15):
            raise ValueError("invalid inventory envelope")
        specs = []
        for row in data["objects"]:
            if not isinstance(row, dict) or set(row) != {"path", "identity", "acl", "directory", "sha256"}:
                raise ValueError("invalid object fields")
            acl = row["acl"]
            if (not isinstance(acl, dict) or set(acl) != {"owner", "aces", "control"}
                    or not isinstance(acl["aces"], list) or len(acl["aces"]) > 1024
                    or any(not isinstance(ace, list) or len(ace) != 4
                           or any(type(value) is not int for value in ace[:3])
                           or not isinstance(ace[3], str) for ace in acl["aces"])
                    or not isinstance(acl["owner"], str) or type(acl["control"]) is not int
                    or not isinstance(row["path"], str) or str(Path(row["path"])) != row["path"]
                    or not isinstance(row["identity"], list) or len(row["identity"]) != 2):
                raise ValueError("invalid object encoding")
            specs.append(ApprovedObject(Path(row["path"]), tuple(row["identity"]),
                                         AclPolicy(acl["owner"], tuple(tuple(ace) for ace in acl["aces"]), acl["control"]),
                                         row["directory"], row["sha256"]))
        specs = tuple(specs)
        _shape(specs, policy, event)
        if raw != encode_inventory(policy, protection, event, specs):
            raise ValueError("noncanonical inventory")
        return VerifiedInventory(event, specs)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise StagingError("invalid or inconsistent protected inventory; HOLD") from None


class ProtectedInventory:
    def __init__(self, protection, boundary):
        if not isinstance(boundary, NativeStoreBoundary):
            raise StagingError("inventory requires the existing Native global Gate; HOLD")
        validate_inventory_policy(boundary.policy, protection)
        self.protection, self.boundary = protection, boundary
        self.root = protection.root.path
        self.recorded = None
        self.initial_names = None

    @contextmanager
    def _operation(self):
        try:
            self.boundary._require_gate()
            self.boundary.checkpoint()
            validate_inventory_policy(self.boundary.policy, self.protection)
            config = self.boundary.api.known_folder() / self.boundary.policy.config_relative
            if self.root.is_relative_to(config) or config.is_relative_to(self.root):
                raise StagingError("inventory area cannot be inside administrator Config; HOLD")
            spec = self.protection.root
            handle, _ = self.boundary.pins[self.root]
            self.boundary._verify(self.boundary.api.info(handle), self.root, spec.acl, True, spec.identity)
            yield
        except BaseException:
            self.boundary.failed = True
            raise

    def _names(self):
        names = self.boundary.api.children(self.boundary.pins[self.root][0])
        if (len(names) > 1024 or len(set(name.casefold() for name in names)) != len(names)
                or any(not _inventory_filename(name) for name in names)):
            raise StagingError("unexpected inventory objects; HOLD")
        return names

    def ensure_creation_available(self):
        """Configuration/capability check before even acquiring a new Gate."""
        capability = getattr(self.boundary.api, "inventory_creation_available", None)
        try:
            available = capability() if callable(capability) else False
        except (OSError, ValueError):
            raise StagingError("protected inventory authority could not be verified; HOLD") from None
        if available is not True:
            raise StagingError("approved protected inventory creation authority missing; HOLD")

    def preflight(self, event):
        with self._operation():
            self.ensure_creation_available()
            names = frozenset(self._names())
            if self.initial_names is None:
                self.initial_names = names
            if names != self.initial_names:
                raise StagingError("inventory namespace changed during attempt; HOLD")
            if _path(self.protection, event).name in names:
                raise StagingError("inventory attempt collision; HOLD")

    def record(self, evidence, pending_bytes, folders, checkpoint):
        with self._operation():
            if self.recorded is not None or not set(folders) <= self.boundary.created_dirs:
                raise StagingError("inventory cannot adopt/rebuild existing remnants; HOLD")
            files = _validated_files(evidence, pending_bytes)
            specs = []
            for folder in folders:
                for path in (folder, *(folder / name for name in sorted(files))):
                    handle, initial = self.boundary.pins[path]
                    current = self.boundary.api.info(handle)
                    self.boundary._verify(current, path, initial.acl, initial.directory, initial.identity)
                    digest = None
                    if not current.directory:
                        raw = self.boundary.api.read(handle, len(files[path.name]) + 1)
                        if raw != files[path.name]:
                            raise StagingError("inventory source bytes changed; HOLD")
                        digest = observation.digest(raw)
                    specs.append(ApprovedObject(path, current.identity, current.acl, current.directory, digest))
            event = _event(evidence.record["evidence_id"])
            payload = encode_inventory(self.boundary.policy, self.protection, event, tuple(specs))
            checkpoint()
            self.preflight(event)
            path = _path(self.protection, event)
            handle = self.boundary.api.create_inventory(path, self.protection.file_acl,
                                                        parent=self.boundary.pins[self.root][0])
            self.boundary._adopt(path, handle, self.protection.file_acl, False)
            self.boundary.checkpoint()  # Final owner/DACL/ID confirmed BEFORE private bytes.
            self.boundary.api.write(handle, payload)
            self.boundary.api.flush(handle)
            self.recorded = (path, payload, event)
            self.verify_record()
            checkpoint()

    def verify_record(self):
        with self._operation():
            if self.recorded is None:
                raise StagingError("inventory record incomplete; HOLD")
            path, payload, event = self.recorded
            if frozenset(self._names()) != self.initial_names | {path.name}:
                raise StagingError("inventory namespace changed during verification; HOLD")
            raw = self.boundary.api.read(self.boundary.pins[path][0], MAX_BYTES + 1)
            if raw != payload:
                raise StagingError("inventory write/readback mismatch; HOLD")
            decode_inventory(raw, self.boundary.policy, self.protection, event)
            self.boundary.checkpoint()


def load_inventory(policy, protection, event, *, api=None):
    """Trust comes from approved root/owner/RO DACL, NEVER a payload self-hash."""
    validate_inventory_policy(policy, protection)
    path = _path(protection, event)
    if api is None:
        from fr_b02b_windows_store import Win32StoreNative
        api = Win32StoreNative(allow_changes=False)
    try:
        with _ReadView(policy, api).opened() as view:
            root = protection.root.path
            config = api.known_folder() / policy.config_relative
            if root.is_relative_to(config) or config.is_relative_to(root):
                raise StagingError("inventory area cannot be inside administrator Config; HOLD")
            names = view.names(root)
            if path.name not in names or any(not _inventory_filename(name) for name in names):
                raise StagingError("missing or unexpected inventory record; HOLD")
            view.check()
            handle = api.open_existing(path, False, True)
            view.boundary._adopt(path, handle, protection.file_acl, False)
            raw = api.read(handle, MAX_BYTES + 1)
            loaded = decode_inventory(raw, policy, protection, event)
            view.check()
            if api.read(handle, MAX_BYTES + 1) != raw or view.names(root) != names:
                raise StagingError("inventory changed while loading; HOLD")
        return loaded
    except (ValueError, OSError):
        raise StagingError("protected inventory could not be trusted; HOLD") from None


def inspect_restart_with_inventory(policy, protection, event, *, api=None):
    try:
        loaded = load_inventory(policy, protection, event, api=api)
    except (ValueError, OSError):
        return RestartAssessment("HOLD", "TRUSTED_INVENTORY_UNAVAILABLE", "UNKNOWN", "NONE")
    return inspect_restart(policy, api=api, expected_objects=loaded.expected_objects)


FINAL_SCHEMA = "PHASE4B2_FINAL_OBJECT_INVENTORY_V1"


class FinalObjectInventory:
    """Append-only final-object attestations, separate from the HOLD contract.

    The injected authority must create administrator-owned, reviewer-read-only
    objects and return retained handles. Win32 supplies NO such authority. A
    manifest/COMPLETE marker alone can never supply these object identities.
    """

    def __init__(self, protection, boundary, *, _read_view=None):
        self.guard = ProtectedInventory(protection, boundary)
        if _read_view is not None and (not isinstance(_read_view, _ReadView)
                or _read_view.boundary is not boundary or boundary.api.allow_changes is not False):
            raise StagingError("invalid read-only final boundary; HOLD")
        self.read_view = _read_view
        self.protection, self.boundary = protection, boundary
        self.root = protection.root.path
        self.records = {}
        self.namespace = None
        self.objects = {}
        if boundary.final_inventory is not None:
            raise StagingError("final inventory already bound; HOLD")
        for root in (boundary.policy.primary, boundary.policy.backup):
            container = next((spec for spec in boundary.policy.anchors
                              if spec.path == root / "registrations" and spec.directory), None)
            if container is None:
                raise StagingError("approved final registration container missing; HOLD")
            _readonly_acl(container.acl, boundary.policy.reviewer_sid, True)
        boundary.final_inventory = self

    @contextmanager
    def _operation(self):
        operation = (self.guard._operation if self.read_view is None else
                     _readonly_final_operation(self.read_view, self.guard))
        with operation():
            yield

    def ensure_creation_available(self):
        if self.read_view is not None or self.boundary.api.allow_changes is not True:
            raise StagingError("read-only final inventory cannot create; HOLD")
        self.guard.ensure_creation_available()
        available = getattr(self.boundary.api, "final_creation_available", None)
        try:
            if not callable(available) or available() is not True:
                raise StagingError("approved final-object creation authority missing; HOLD")
        except (OSError, ValueError):
            raise StagingError("approved final-object creation authority unavailable; HOLD") from None

    def is_final_path(self, path, *, directory):
        from fr_b02b_registration import REGISTRATION_FILES, BASE_FILES, _id
        for root in (self.boundary.policy.primary, self.boundary.policy.backup):
            if path.parent == root and directory and path.name.startswith(".review-registration-restore-"):
                _id(path.name.removeprefix(".review-registration-restore-"))
                return True
            if path.parent.parent == root and path.parent.name.startswith(".review-registration-restore-"):
                _id(path.parent.name.removeprefix(".review-registration-restore-"))
                return not directory and path.name in BASE_FILES
            container = root / "registrations"
            if not path.is_relative_to(container):
                continue
            parts = path.relative_to(container).parts
            if not parts:
                return False
            _id(parts[0])
            if len(parts) == 1:
                return directory
            if len(parts) == 2:
                return (directory and parts[1] == "revocations") or (not directory and parts[1] in REGISTRATION_FILES)
            if len(parts) == 3 and parts[1] == "revocations" and not directory:
                return bool(re.fullmatch(r"REV-OBS-[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\.json", parts[2]))
        return False

    def create(self, path, *, directory):
        with self._operation():
            self.ensure_creation_available()
            if not self.is_final_path(path, directory=directory):
                raise StagingError("unapproved final-object layout; HOLD")
            acl = self.protection.root.acl if directory else self.protection.file_acl
            handle = self.boundary.api.create_final(path, acl, directory=directory,
                                                   parent=self.boundary.pins[path.parent][0])
            self.boundary._adopt(path, handle, acl, directory)
            self.boundary.checkpoint()  # Confirm owner/DACL/ID BEFORE any bytes.
            if directory:
                self.boundary.created_dirs.add(path)

    def _names(self, path):
        names = self.boundary.api.children(self.boundary.pins[path][0])
        if (not isinstance(names, (tuple, list)) or len(names) > 1024
                or any(not isinstance(name, str) or not name or name in (".", "..")
                       or any(char in name for char in "\\/:\x00") for name in names)
                or len({name.casefold() for name in names}) != len(names)):
            raise StagingError("invalid final-object namespace; HOLD")
        return frozenset(names)

    def _inventory_names(self):
        names = self._names(self.root)
        if any(not _inventory_filename(name) for name in names):
            raise StagingError("unexpected protected inventory objects; HOLD")
        return names

    def _shape(self, kind, rid, eid, specs):
        from fr_b02b_registration import REGISTRATION_FILES, BASE_FILES, _id
        from uuid import UUID
        _id(rid)
        expected = set()
        roots = (self.boundary.policy.primary, self.boundary.policy.backup)
        if kind == "REGISTRATION" and eid == rid:
            for root in roots:
                folder = root / "registrations" / rid
                expected.update((folder, *(folder / name for name in REGISTRATION_FILES)))
            restores = [spec.path for spec in specs if spec.directory
                        and spec.path.name == ".review-registration-restore-" + rid
                        and spec.path.parent in roots]
            if len(restores) != 1:
                raise StagingError("final inventory requires one verified restore; HOLD")
            folder = restores[0]
            expected.update((folder, *(folder / name for name in BASE_FILES)))
        elif kind == "REVOCATION" and isinstance(eid, str) and re.fullmatch(r"REV-OBS-[0-9a-f]{32}", eid):
            if UUID(eid.removeprefix("REV-OBS-")).version != 4:
                raise StagingError("invalid revocation inventory ID; HOLD")
            for root in roots:
                folder = root / "registrations" / rid / "revocations"
                expected.update((folder, folder / (eid + ".json")))
        else:
            raise StagingError("invalid final inventory kind; HOLD")
        known = {}
        for spec in specs:
            if (not isinstance(spec, ApprovedObject) or spec.path not in expected or spec.path in known
                    or type(spec.directory) is not bool or not isinstance(spec.identity, tuple)
                    or len(spec.identity) != 2 or type(spec.identity[0]) is not int
                    or not 0 <= spec.identity[0] <= 0xFFFFFFFFFFFFFFFF
                    or not isinstance(spec.identity[1], str)
                    or not re.fullmatch(r"[0-9a-f]{32}", spec.identity[1]) or spec.identity[1] == "0" * 32
                    or not self.is_final_path(spec.path, directory=spec.directory)
                    or spec.acl != (self.protection.root.acl if spec.directory else self.protection.file_acl)
                    or (spec.sha256 is not None if spec.directory else
                        not isinstance(spec.sha256, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", spec.sha256))):
                raise StagingError("invalid final inventory object; HOLD")
            _readonly_acl(spec.acl, self.boundary.policy.reviewer_sid, spec.directory)
            known[spec.path] = spec
        if set(known) != expected:
            raise StagingError("incomplete final inventory objects; HOLD")
        hashes = {}
        for spec in specs:
            if not spec.directory:
                hashes.setdefault(spec.path.name, set()).add(spec.sha256)
        if any(len(values) != 1 for values in hashes.values()):
            raise StagingError("final C/E/restore inventory hashes disagree; HOLD")
        return known

    def _encode(self, kind, rid, eid, specs):
        self._shape(kind, rid, eid, specs)
        raw = observation.canonical_bytes(dict(schema=FINAL_SCHEMA, kind=kind,
            registration_id=rid, event_id=eid, publish_authorization="NONE",
            policy_binding=_binding(self.boundary.policy, self.protection),
            objects=[_plain(spec) for spec in sorted(specs, key=lambda item: str(item.path))]))
        if len(raw) > MAX_BYTES:
            raise StagingError("final inventory too large; HOLD")
        return raw

    def _decode(self, raw, filename):
        try:
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
                raise ValueError("size")
            data = json.loads(raw)
            if (set(data) != {"schema", "kind", "registration_id", "event_id", "publish_authorization",
                             "policy_binding", "objects"}
                    or data["schema"] != FINAL_SCHEMA or data["publish_authorization"] != "NONE"
                    or data["policy_binding"] != _binding(self.boundary.policy, self.protection)
                    or filename != "final-" + data["event_id"] + ".json"
                    or not isinstance(data["objects"], list) or len(data["objects"]) > 32):
                raise ValueError("envelope")
            specs = []
            for row in data["objects"]:
                if set(row) != {"path", "identity", "acl", "directory", "sha256"}:
                    raise ValueError("object fields")
                acl = row["acl"]
                if set(acl) != {"owner", "aces", "control"}:
                    raise ValueError("ACL fields")
                specs.append(ApprovedObject(Path(row["path"]), tuple(row["identity"]),
                    AclPolicy(acl["owner"], tuple(tuple(ace) for ace in acl["aces"]), acl["control"]),
                    row["directory"], row["sha256"]))
            specs = tuple(specs)
            if raw != self._encode(data["kind"], data["registration_id"], data["event_id"], specs):
                raise ValueError("noncanonical")
            return self._shape(data["kind"], data["registration_id"], data["event_id"], specs)
        except (ValueError, TypeError, KeyError, RecursionError):
            raise StagingError("invalid protected final inventory; HOLD") from None

    def _adopt(self, spec):
        if spec.path not in self.boundary.pins:
            handle = self.boundary.api.open_existing(spec.path, spec.directory, not spec.directory)
            self.boundary._adopt(spec.path, handle, spec.acl, spec.directory, spec.identity)
        handle, _ = self.boundary.pins[spec.path]
        self.boundary._verify(self.boundary.api.info(handle), spec.path, spec.acl, spec.directory, spec.identity)
        if not spec.directory:
            limit = 20 * 1024 * 1024 if spec.path.name == "a1_archive.zip" else MAX_BYTES
            raw = self.boundary.api.read(handle, limit + 1)
            if len(raw) > limit or observation.digest(raw) != spec.sha256:
                raise StagingError("final inventory hash mismatch; HOLD")

    def verify_existing(self):
        """Load trust from protected records BEFORE scanning final history."""
        with self._operation():
            names = self._inventory_names()
            if self.namespace is not None:
                self.check()
            objects, records = {}, {}
            for name in sorted(names):
                if not name.startswith("final-"):
                    continue  # HOLD objects retain their separate validator.
                path = self.root / name
                if path not in self.boundary.pins:
                    handle = self.boundary.api.open_existing(path, False, True)
                    self.boundary._adopt(path, handle, self.protection.file_acl, False)
                raw = self.boundary.api.read(self.boundary.pins[path][0], MAX_BYTES + 1)
                known = self._decode(raw, name)
                if objects.keys() & known.keys():
                    raise StagingError("conflicting final inventory records; HOLD")
                for spec in sorted(known.values(), key=lambda item: len(item.path.parts)):
                    self._adopt(spec)
                objects.update(known)
                records[path] = raw
            # Compare complete namespaces, including absence on BOTH disks.
            for root in (self.boundary.policy.primary, self.boundary.policy.backup):
                container = root / "registrations"
                expected = {path.name for path in objects if path.parent == container}
                if self._names(container) != expected:
                    raise StagingError("unsealed/missing final registration; HOLD")
                restores = {path.name for path in objects if path.parent == root}
                root_names = self._names(root)
                actual = {name for name in root_names if name.startswith(".review-registration-restore-")}
                anchors = {spec.path.name for spec in self.boundary.policy.anchors if spec.path.parent == root}
                if any(name not in anchors | restores and not re.fullmatch(
                        r"\.review-(?:staging|restore)-LOCAL-OBS-[0-9a-f]{32}", name) for name in root_names):
                    raise StagingError("unexpected final store root object; HOLD")
                if actual != restores:
                    raise StagingError("unsealed/missing registration restore; HOLD")
            for path, spec in objects.items():
                if spec.directory and self._names(path) != {p.name for p in objects if p.parent == path}:
                    raise StagingError("unsealed/missing final history member; HOLD")
            self.records, self.objects, self.namespace = records, objects, names
            self.check()

    def check(self):
        with self._operation():
            if self.namespace is None or self._inventory_names() != self.namespace:
                raise StagingError("final inventory namespace changed; HOLD")
            for path, raw in self.records.items():
                if self.boundary.api.read(self.boundary.pins[path][0], MAX_BYTES + 1) != raw:
                    raise StagingError("final inventory bytes changed; HOLD")
            for spec in self.objects.values():
                self._adopt(spec)
                if spec.directory:
                    expected = {path.name for path in self.objects if path.parent == spec.path}
                    # Only a NEW revocation directory may extend a sealed
                    # registration in flight. History separately tracks it and
                    # no verdict is returned until its own seal is persisted.
                    expected |= {path.name for path in self.boundary.created_dirs
                                 if path.parent == spec.path and path.name == "revocations"}
                    if self._names(spec.path) != expected:
                        raise StagingError("final object namespace changed; HOLD")
            self.boundary.checkpoint()

    def record(self, kind, rid, eid, paths):
        with self._operation():
            self.ensure_creation_available()
            self.check()
            specs = []
            for path in paths:
                if path not in self.boundary.pins or path in self.objects:
                    raise StagingError("cannot reseal/adopt final history; HOLD")
                handle, initial = self.boundary.pins[path]
                if initial.directory and path not in self.boundary.created_dirs:
                    raise StagingError("final directory not created by this attempt; HOLD")
                self.boundary._verify(self.boundary.api.info(handle), path, initial.acl,
                                      initial.directory, initial.identity)
                limit = 20 * 1024 * 1024 if path.name == "a1_archive.zip" else MAX_BYTES
                raw = None if initial.directory else self.boundary.api.read(handle, limit + 1)
                if raw is not None and len(raw) > limit:
                    raise StagingError("final source too large; HOLD")
                specs.append(ApprovedObject(path, initial.identity, initial.acl, initial.directory,
                                             None if raw is None else observation.digest(raw)))
            payload = self._encode(kind, rid, eid, tuple(specs))
            path = self.root / ("final-" + eid + ".json")
            if path.name in self.namespace:
                raise StagingError("final inventory collision; HOLD")
            handle = self.boundary.api.create_inventory(path, self.protection.file_acl,
                                                        parent=self.boundary.pins[self.root][0])
            self.boundary._adopt(path, handle, self.protection.file_acl, False)
            self.boundary.checkpoint()
            self.boundary.api.write(handle, payload)
            self.boundary.api.flush(handle)
            if self.boundary.api.read(handle, MAX_BYTES + 1) != payload:
                raise StagingError("partial final inventory record; HOLD")
            self.namespace = self.namespace | {path.name}
            self.records[path] = payload
            self.verify_existing()


def inspect_final_history(policy, protection, *, api=None, registration_id=None):
    """Fresh read-only observation; still HOLD and requires a Gate recheck."""
    from fr_b02b_registration import RegistrationHistory
    try:
        validate_inventory_policy(policy, protection)
        if api is None:
            from fr_b02b_windows_store import Win32StoreNative
            api = Win32StoreNative(allow_changes=False)
        view = _ReadView(policy, api)
        FinalObjectInventory(protection, view.boundary, _read_view=view)
        # Read-only view never claims to acquire the writer Gate.
        with view.opened():
            from fr_b02b_native_store import NativeProtectedStore

            class ReadOnlyStore(NativeProtectedStore):
                def _checked(self, path, *, directory):
                    view.check()
                    if path not in view.boundary.pins:
                        raise StagingError("untrusted read-only final object; HOLD")
                    handle, initial = view.boundary.pins[path]
                    view.boundary._verify(view.api.info(handle), path, initial.acl, directory, initial.identity)
                    return path

                def _read_copy(self, path, limit):
                    self._checked(path, directory=False)
                    raw = view.api.read(view.boundary.pins[path][0], limit)
                    self._checked(path, directory=False)
                    return raw

            stores = tuple(ReadOnlyStore(root, view.boundary) for root in (policy.primary, policy.backup))
            history = RegistrationHistory(stores, revalidate_input=view.check)
            history.check()
            state = None
            if registration_id is not None:
                row = history.manifests[registration_id]
                state = "REVOKED" if history.revocations[registration_id] else row["review_result"]
            result = RestartAssessment("HOLD", "REGISTRATION_HISTORY_VERIFIED_RECHECK_REQUIRED",
                view.gate_status, "CONTENT_VERIFIED", effective_review_state=state)
        return result
    except (ValueError, OSError, KeyError, TypeError):
        return RestartAssessment("HOLD", "REGISTRATION_HISTORY_UNVERIFIED", "UNKNOWN", "NONE")


def _readonly_final_operation(view, guard):
    @contextmanager
    def operation():
        view.check()
        config = view.api.known_folder() / view.policy.config_relative
        if guard.root.is_relative_to(config) or config.is_relative_to(guard.root):
            raise StagingError("inventory overlaps Config; HOLD")
        yield
        view.check()
    return operation
