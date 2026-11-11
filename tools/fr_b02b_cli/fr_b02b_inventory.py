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
                or any(not re.fullmatch(r"inventory-LOCAL-OBS-[0-9a-f]{32}\.json", name) for name in names)):
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
            if (path.name not in names or any(not re.fullmatch(
                    r"inventory-LOCAL-OBS-[0-9a-f]{32}\.json", name) for name in names)):
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
