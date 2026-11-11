"""Read-only, UNSERIALIZED restart observations. Never a registration/recovery API.

An empty observation permits considering a new attempt, not writing without its
global Gate and fresh checks. Existing objects need an independently trusted
private inventory: inspected bytes/IDs cannot approve themselves. Its production
loader/persistence is deliberately absent. No Gate acquisition, repair or cleanup.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import re

import fr_b02b_observation as observation
from fr_b02b_native_store import ApprovedObject, NativeError, NativeStoreBoundary, _policy_valid
from fr_b02b_protected_store import StagingError
from fr_b02b_restore import validate_stored_files

FILES = frozenset({"a1_archive.zip", "observation.json", "index.json", "pending_review.json"})
COMPLETION = frozenset({"registration.json", "registration_complete.json"})


@dataclass(frozen=True)
class RestartAssessment:
    classification: str
    reason: str
    gate_status: str
    inspection_scope: str
    may_attempt_new_work: bool = False
    valid_registration: bool = field(default=False, init=False)
    publish_authorization: str = field(default="NONE", init=False)
    requires_gate_recheck: bool = field(default=True, init=False)


class _Issue(StagingError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__("restart state remains HOLD")


class _ReadView:
    def __init__(self, policy, api):
        if api.allow_changes is not False:
            raise _Issue("READ_ONLY_CAPABILITY_REQUIRED")
        gate = policy.control / "global.gate"
        if any(spec.path.is_relative_to(gate) for spec in policy.anchors):
            raise _Issue("INVALID_PRIVATE_GATE_POLICY")
        self.boundary = NativeStoreBoundary(policy, api)  # Fresh pins; never writer memory.
        self.api, self.policy = api, policy
        self.gate_status, self.scope = "UNKNOWN", "NONE"

    @contextmanager
    def opened(self):
        boundary = self.boundary
        boundary.spent = True
        try:
            for spec in sorted(self.policy.anchors, key=lambda item: len(item.path.parts)):
                handle = self.api.open_existing(spec.path, spec.directory, not spec.directory)
                boundary._adopt(spec.path, handle, spec.acl, spec.directory, spec.identity)
            boundary.checkpoint()  # Reuse the read-only bootstrap, NOT its Gate section.
            self.scope = "ANCHORS_ONLY"
            self.check()
            yield self
            self.check()
        finally:
            boundary._close(tuple(boundary.pins))

    def check(self):
        self.boundary.checkpoint()
        try:
            present = self.api.exists(self.boundary.gate)  # Attributes only; never open Gate.
        except (OSError, ValueError):
            self.gate_status = "UNKNOWN"
            raise
        if type(present) is not bool:
            raise _Issue("UNVERIFIED_GATE")
        self.gate_status = "PRESENT" if present else "ABSENT_OBSERVED"
        if present:
            raise _Issue("GATE_PRESENT")

    def names(self, path):
        self.check()
        names = self.api.children(self.boundary.pins[path][0])
        if (not isinstance(names, (tuple, list)) or len(names) > 1024
                or any(not isinstance(name, str) or not name or name in (".", "..")
                       or any(char in name for char in "\\/:\x00") for name in names)
                or len({name.casefold() for name in names}) != len(names)):
            raise _Issue("UNEXPECTED_OBJECT")
        self.check()
        return frozenset(names)

    def adopt(self, spec):
        self.check()
        handle = self.api.open_existing(spec.path, spec.directory, not spec.directory)
        try:
            self.boundary._adopt(spec.path, handle, spec.acl, spec.directory, spec.identity)
        except NativeError:
            raise
        except StagingError:
            raise _Issue("OBJECT_POLICY_MISMATCH") from None
        self.check()

    def read(self, spec):
        self.check()
        limit = 20 * 1024 * 1024 if spec.path.name == "a1_archive.zip" else observation.MAX_RECORD_BYTES
        raw = self.api.read(self.boundary.pins[spec.path][0], limit + 1)
        if not isinstance(raw, bytes) or len(raw) > limit or observation.digest(raw) != spec.sha256:
            raise _Issue("BYTE_HASH_MISMATCH")
        self.check()
        return raw


def _inventory(specs, policy):
    if not isinstance(specs, tuple) or len(specs) > 10000:
        raise _Issue("INVALID_TRUSTED_INVENTORY")
    result = {}
    for spec in specs:
        if (not isinstance(spec, ApprovedObject) or not isinstance(spec.path, Path)
                or not spec.path.is_absolute() or ".." in spec.path.parts
                or type(spec.directory) is not bool or spec.path in result
                or not isinstance(spec.identity, tuple) or len(spec.identity) != 2
                or type(spec.identity[0]) is not int
                or not 0 <= spec.identity[0] <= 0xFFFFFFFFFFFFFFFF
                or not isinstance(spec.identity[1], str)
                or not re.fullmatch(r"[0-9a-f]{32}", spec.identity[1])
                or spec.identity[1] == "0" * 32):
            raise _Issue("INVALID_TRUSTED_INVENTORY")
        parent = spec.path.parent if spec.directory else spec.path.parent.parent
        if (parent not in (policy.primary, policy.backup)
                or spec.acl != (policy.staging_acl if spec.directory else policy.file_acl)
                or (not spec.directory and (spec.path.name not in FILES
                    or not isinstance(spec.sha256, str)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", spec.sha256)))):
            raise _Issue("INVALID_TRUSTED_INVENTORY")
        result[spec.path] = spec
    return result


def _inspect(view, expected_objects):
    roots = (view.policy.primary, view.policy.backup)
    inventory = _inventory(expected_objects, view.policy) if expected_objects is not None else None
    control_names = frozenset(spec.path.name for spec in view.policy.anchors
                              if spec.path.parent == view.policy.control)
    if view.names(view.policy.control) != control_names:
        raise _Issue("UNEXPECTED_CONTROL_OBJECT")
    namespace = {root: view.names(root) for root in roots}
    view.scope = "NAMES_ONLY"
    if not any(namespace.values()):
        if inventory:
            raise _Issue("INVENTORY_OBJECTS_MISSING")
        if (view.names(view.policy.control) != control_names
                or any(view.names(root) != names for root, names in namespace.items())):
            raise _Issue("NAMESPACE_CHANGED")
        return RestartAssessment("INITIAL_EMPTY", "EMPTY_AT_OBSERVATION", view.gate_status,
                                 "EMPTY_NAMES", True)
    groups, event_ids = {}, set()
    for root, names in namespace.items():
        for name in names:
            if name in COMPLETION:
                raise _Issue("UNSUPPORTED_COMPLETION")
            match = re.fullmatch(r"\.review-(staging|restore)-(LOCAL-OBS-[0-9a-f]{32})", name)
            if not match:
                raise _Issue("UNEXPECTED_OBJECT")
            kind, event_id = match.groups()
            event_ids.add(event_id)
            groups[root / name] = (kind, event_id)
    if len(event_ids) != 1:
        raise _Issue("DUPLICATE_HISTORY_SUSPECTED")
    event_id = next(iter(event_ids))
    if any(root / (".review-staging-" + event_id) not in groups for root in roots):
        raise _Issue("PARTIAL_CE_STAGING")
    if expected_objects is None:
        raise _Issue("TRUSTED_INVENTORY_REQUIRED")
    actual_paths, snapshots = set(), {}
    for folder, (_, current_id) in sorted(groups.items()):
        spec = inventory.get(folder)
        if spec is None or not spec.directory:
            raise _Issue("INVENTORY_OBJECTS_MISMATCH")
        view.adopt(spec)
        names = view.names(folder)
        if names & COMPLETION:
            raise _Issue("UNSUPPORTED_COMPLETION")
        if names != FILES:
            raise _Issue("PARTIAL_OR_UNEXPECTED_FILES")
        actual_paths.add(folder)
        snapshot = {}
        for name in sorted(names):
            path = folder / name
            spec = inventory.get(path)
            if spec is None or spec.directory:
                raise _Issue("INVENTORY_OBJECTS_MISMATCH")
            view.adopt(spec)
            snapshot[name] = view.read(spec)
            actual_paths.add(path)
        try:
            validate_stored_files(snapshot, current_id)  # Shared Restore/A1/4A validation.
        except StagingError:
            raise _Issue("INVALID_STORED_LINKS") from None
        snapshots[folder] = snapshot
    if actual_paths != set(inventory):
        raise _Issue("INVENTORY_OBJECTS_MISMATCH")
    reference = next(iter(snapshots.values()))
    if any(snapshot != reference for snapshot in snapshots.values()):
        raise _Issue("CE_RESTORE_BYTES_MISMATCH")
    # Re-enumerate and re-read on the SAME held handles. Gate absence is still
    # only observed: this cannot exclude an intervening/ABA writer or admin.
    for root, names in namespace.items():
        if view.names(root) != names:
            raise _Issue("NAMESPACE_CHANGED")
    for folder, snapshot in snapshots.items():
        if view.names(folder) != FILES:
            raise _Issue("NAMESPACE_CHANGED")
        if any(view.read(inventory[folder / name]) != raw for name, raw in snapshot.items()):
            raise _Issue("BYTE_HASH_MISMATCH")
    if view.names(view.policy.control) != control_names:
        raise _Issue("NAMESPACE_CHANGED")
    view.scope = "CONTENT_VERIFIED"
    return RestartAssessment("HOLD", "UNCOMPLETED_HOLD", view.gate_status, view.scope)


def inspect_restart(policy=None, *, api=None, expected_objects=None):
    """No registration can be accepted. No result is a reusable write permit."""
    view = None
    try:
        _policy_valid(policy)  # No configured policy => no DLL or filesystem calls.
        if api is None:
            from fr_b02b_windows_store import Win32StoreNative
            api = Win32StoreNative(allow_changes=False)
        view = _ReadView(policy, api)
        with view.opened():
            result = _inspect(view, expected_objects)
        return result  # Close failure must prevent INITIAL_EMPTY being returned.
    except _Issue as error:
        reason = error.reason
    except NativeError as error:
        reason = {5: "ACCESS_DENIED", 32: "SHARING_BLOCKED", 2: "MISSING_OBJECT",
                  3: "MISSING_OBJECT"}.get(error.code, "NATIVE_READ_FAILED")
    except (StagingError, OSError):
        reason = "UNVERIFIED_ENVIRONMENT"
    return RestartAssessment("HOLD", reason, view.gate_status if view else "UNKNOWN",
                             view.scope if view else "NONE")
