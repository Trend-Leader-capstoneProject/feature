"""Native HOLD boundary. Trusted private policy is required; no operating defaults.

Policy is supplied by a trusted bootstrap, never derived from the settings being
verified. No CLI/config loader, ACL repair or completed registration.
All handles are retained without delete sharing. Local administrators can still
change ACLs/restore them (ABA); this is not an independent immutable seal.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
import re

import fr_b02b_observation as observation
from fr_b02b_protected_store import (
    MirroredEvidenceStore, ProtectedEvidenceStore, StagingError,
)


class NativeError(StagingError):
    def __init__(self, code):
        self.code = int(code)
        super().__init__("native protected operation failed; HOLD")


def _guarded(operation):
    @wraps(operation)
    def guarded(self, *args, **kwargs):
        try:
            self._require_gate()
            return operation(self, *args, **kwargs)
        except BaseException:
            self.failed = True
            raise
    return guarded


@dataclass(frozen=True, repr=False)
class AclPolicy:
    owner: str
    aces: tuple[tuple[int, int, int, str], ...]  # type, flags, mask, SID; exact order
    control: int  # DACL_PRESENT, AUTO_INHERIT_REQ, AUTO_INHERITED, PROTECTED


@dataclass(frozen=True, repr=False)
class ObjectInfo:
    path: Path
    identity: tuple[int, str]  # 64-bit volume serial, 128-bit File ID
    acl: AclPolicy
    directory: bool
    reparse: bool
    links: int


@dataclass(frozen=True, repr=False)
class ApprovedObject:
    path: Path
    identity: tuple[int, str]
    acl: AclPolicy
    directory: bool
    sha256: str | None = None  # Config/Allowlist bytes, approved OUTSIDE this file


@dataclass(frozen=True, repr=False)
class VolumeInfo:
    guid: str
    serial: int
    disks: tuple[int, ...]


@dataclass(frozen=True, repr=False)
class StorePolicy:
    reviewer_sid: str
    anchors: tuple[ApprovedObject, ...]  # Every existing ancestor + protected config files
    primary: Path
    backup: Path
    control: Path  # Fixed global coordination container; not derived from Store
    config_relative: str  # Approved relative boundary under ProgramData Known Folder
    primary_volume: VolumeInfo
    backup_volume: VolumeInfo
    staging_acl: AclPolicy
    file_acl: AclPolicy
    gate_acl: AclPolicy


def _policy_valid(policy):
    if (not isinstance(policy, StorePolicy) or not isinstance(policy.reviewer_sid, str)
            or not isinstance(policy.anchors, tuple)
            or any(not isinstance(item, ApprovedObject) for item in policy.anchors)
            or not isinstance(policy.config_relative, str)
            or any(not isinstance(path, Path) for path in (policy.primary, policy.backup, policy.control))):
        raise StagingError("trusted protected storage policy missing; HOLD")
    paths = [item.path for item in policy.anchors]
    relative = Path(policy.config_relative)
    if (not re.fullmatch(r"S-1-(?:\d+-)+\d+", policy.reviewer_sid)
            or not policy.anchors or len(set(paths)) != len(paths)
            or not policy.config_relative or not relative.parts or relative.is_absolute()
            or relative.root or relative.drive
            or any(part in ("..", ".") or ":" in part for part in relative.parts)):
        raise StagingError("invalid private boundary policy; HOLD")
    for item in policy.anchors:
        if (not isinstance(item.path, Path) or not item.path.is_absolute()
                or not re.fullmatch(r"[A-Za-z]:", item.path.drive)
                or ".." in item.path.parts or any(":" in p for p in item.path.parts[1:])
                or not isinstance(item.identity, tuple) or len(item.identity) != 2
                or type(item.identity[0]) is not int or not isinstance(item.identity[1], str)
                or not 0 <= item.identity[0] <= 0xFFFFFFFFFFFFFFFF
                or not re.fullmatch(r"[0-9a-f]{32}", item.identity[1])
                or item.identity[1] == "0" * 32
                or (not item.directory and not re.fullmatch(r"sha256:[0-9a-f]{64}", item.sha256 or ""))
                or any(parent not in paths for parent in item.path.parents)):
            raise StagingError("incomplete approved object/ancestor policy; HOLD")
    for root in (policy.primary, policy.backup, policy.control):
        if len(root.parts) <= 1 or not any(item.path == root and item.directory for item in policy.anchors):
            raise StagingError("approved root policy missing; HOLD")
    if (policy.primary.is_relative_to(policy.backup) or policy.backup.is_relative_to(policy.primary)
            or policy.control.is_relative_to(policy.primary)
            or policy.control.is_relative_to(policy.backup)
            or policy.primary.is_relative_to(policy.control)
            or policy.backup.is_relative_to(policy.control)):
        raise StagingError("overlapping protected coordination/storage boundaries; HOLD")
    for acl in (*[item.acl for item in policy.anchors], policy.staging_acl,
                policy.file_acl, policy.gate_acl):
        if (not isinstance(acl, AclPolicy) or not isinstance(acl.aces, tuple) or not acl.aces
                or type(acl.control) is not int or not isinstance(acl.owner, str)
                or any(not isinstance(ace, tuple) or len(ace) != 4
                       or any(type(value) is not int for value in ace[:3])
                       or not isinstance(ace[3], str) for ace in acl.aces)
                or acl.control & ~0x1504
                or not acl.control & 4
                or not re.fullmatch(r"S-1-(?:\d+-)+\d+", acl.owner)
                or any(kind not in (0, 1) or not 0 <= flags <= 0x1F
                       or not 0 < mask <= 0xFFFFFFFF
                       or not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid)
                       for kind, flags, mask, sid in acl.aces)):
            raise StagingError("unsupported approved owner/DACL policy; HOLD")
    for acl in (policy.staging_acl, policy.file_acl, policy.gate_acl):
        if acl.control != 0x1004 or any(flags for _, flags, _, _ in acl.aces):
            raise StagingError("new objects require explicit protected DACL; HOLD")
        allowed = {policy.reviewer_sid, "S-1-5-32-544", "S-1-5-18"}
        if (acl.owner not in allowed or any(sid not in allowed for _, _, _, sid in acl.aces)
                or any(kind == 0 and sid == policy.reviewer_sid and mask & 0xF00C0040
                       for kind, _, mask, sid in acl.aces)):
            raise StagingError("new object grants exceed restricted reviewer policy; HOLD")
    for volume in (policy.primary_volume, policy.backup_volume):
        if (not isinstance(volume, VolumeInfo) or not isinstance(volume.guid, str) or not volume.guid
                or not isinstance(volume.disks, tuple) or not volume.disks
                or type(volume.serial) is not int or not 0 <= volume.serial <= 0xFFFFFFFFFFFFFFFF
                or len(set(volume.disks)) != len(volume.disks)
                or any(type(disk) is not int or disk < 0 for disk in volume.disks)):
            raise StagingError("approved disk/volume policy missing; HOLD")
    if (policy.primary_volume.guid == policy.backup_volume.guid
            or set(policy.primary_volume.disks) & set(policy.backup_volume.disks)):
        raise StagingError("protected volumes are not on independent disks; HOLD")


class NativeStoreBoundary:
    def __init__(self, policy, api):
        _policy_valid(policy)
        self.policy, self.api = policy, api
        self.pins = {}
        self.active = self.spent = False
        self.failed = False
        self.created_dirs = set()
        self.gate = policy.control / "global.gate"

    def mirrored_store(self):
        return MirroredEvidenceStore(
            NativeProtectedStore(self.policy.primary, self),
            NativeProtectedStore(self.policy.backup, self),
            verify_layout=self.verify_layout, exclusive_section=self.exclusive_section)

    def _verify(self, info, path, acl, directory, identity=None):
        if (not isinstance(info, ObjectInfo) or info.path != path or info.reparse
                or info.directory is not directory or (not directory and info.links != 1)
                or info.acl != acl or info.identity[1] == "0" * 32
                or type(info.identity[0]) is not int or not 0 <= info.identity[0] <= 0xFFFFFFFFFFFFFFFF
                or not re.fullmatch(r"[0-9a-f]{32}", info.identity[1])
                or (identity is not None and info.identity != identity)):
            raise StagingError("native identity/path/ACL mismatch; HOLD")

    def _adopt(self, path, handle, acl, directory, identity=None):
        try:
            info = self.api.info(handle)
            self._verify(info, path, acl, directory, identity)
            if path.parent in self.pins and info.identity[0] != self.pins[path.parent][1].identity[0]:
                raise StagingError("new object is outside parent volume; HOLD")
            if path in self.pins:
                raise StagingError("duplicate Native object; HOLD")
            self.pins[path] = (handle, info)
        except BaseException:
            self.api.close(handle)  # Preserve object; never delete a failed creation.
            raise

    def _require_gate(self):
        if not self.active or self.failed or self.gate not in self.pins:
            raise StagingError("Native global Gate is absent or attempt failed; HOLD")
        handle, initial = self.pins[self.gate]
        self._verify(self.api.info(handle), self.gate, initial.acl, False, initial.identity)

    def checkpoint(self):
        try:
            self._checkpoint()
        except BaseException:
            if self.active:
                self.failed = True
            raise

    def _checkpoint(self):
        if self.failed:
            raise StagingError("failed Native attempt cannot release Gate normally; HOLD")
        if self.api.sid() != self.policy.reviewer_sid:
            raise StagingError("native reviewer identity changed; HOLD")
        folder = self.api.known_folder()
        config = folder / self.policy.config_relative
        if (config not in self.pins or not self.pins[config][1].directory
                or not self.policy.control.is_relative_to(folder)
                or any(config.is_relative_to(root) or root.is_relative_to(config)
                       for root in (self.policy.primary, self.policy.backup))
                or not any(not item.directory and item.path.is_relative_to(config)
                           for item in self.policy.anchors)):
            raise StagingError("trusted Known Folder bootstrap mismatch; HOLD")
        # Config remains administrator-managed/read-only to R. Store/Control
        # containers cannot grant R ownership/ACL changes or container deletion.
        admins = {"S-1-5-32-544", "S-1-5-18"}
        for spec in self.policy.anchors:
            is_config = spec.path.is_relative_to(config) or not spec.directory
            if not is_config and spec.path not in (self.policy.primary, self.policy.backup, self.policy.control):
                continue
            forbidden = 0xF00D0156 if is_config else 0xF00D0040
            if (spec.acl.owner not in admins or not spec.acl.control & 0x1000
                    or any(kind == 0 and sid not in admins
                           and (sid != self.policy.reviewer_sid or mask & forbidden)
                           for kind, _, mask, sid in spec.acl.aces)):
                raise StagingError("unrestricted protected Config/container policy; HOLD")
        for root in (self.policy.primary, self.policy.backup, self.policy.control, config):
            observation._safe_local_path(root)  # Supplement Native checks: no Git/ambiguous paths.
        for path, (handle, initial) in tuple(self.pins.items()):
            current = self.api.info(handle)
            self._verify(current, path, initial.acl, initial.directory, initial.identity)
        for spec in self.policy.anchors:
            if not spec.directory:
                raw = self.api.read(self.pins[spec.path][0], 65537)
                if len(raw) > 65536 or observation.digest(raw) != spec.sha256:
                    raise StagingError("protected configuration bytes changed; HOLD")
        for root, expected in ((self.policy.primary, self.policy.primary_volume),
                               (self.policy.backup, self.policy.backup_volume)):
            if self.api.volume(self.pins[root][0]) != expected:
                raise StagingError("native volume/disk identity changed; HOLD")
            if self.pins[root][1].identity[0] != expected.serial:
                raise StagingError("root volume serial mismatch; HOLD")

    def verify_layout(self, primary, backup):
        if not self.active or (primary, backup) != (self.policy.primary, self.policy.backup):
            raise StagingError("Native protected section inactive; HOLD")
        self.checkpoint()
        return True

    def _close(self, paths):
        failed = False
        for path in reversed(tuple(paths)):
            handle, _ = self.pins.pop(path)
            try:
                self.api.close(handle)
            except (OSError, ValueError):
                failed = True
        if failed:
            raise StagingError("Native handle release uncertain; HOLD")

    @contextmanager
    def exclusive_section(self):
        if self.spent or self.active:
            raise StagingError("Native attempt cannot be resumed or retried; HOLD")
        self.spent = True
        try:
            for spec in sorted(self.policy.anchors, key=lambda item: len(item.path.parts)):
                handle = self.api.open_existing(spec.path, spec.directory, not spec.directory)
                self._adopt(spec.path, handle, spec.acl, spec.directory, spec.identity)
            self.checkpoint()  # Complete read-only bootstrap BEFORE Gate creation.
            if self.api.allow_changes is not True:
                raise StagingError("Native mutation capability absent; HOLD")
            gate = self.api.create(self.gate, self.policy.gate_acl, gate=True)
            self._adopt(self.gate, gate, self.policy.gate_acl, False)
            self.active = True
            self.checkpoint()  # Same settings/token/IDs after global acquisition.
            yield
            self.checkpoint()
            anchors = {spec.path for spec in self.policy.anchors}
            self._close([path for path in self.pins if path not in anchors and path != self.gate])
            self.checkpoint()
            # Delete only the handle created by THIS attempt after normal completion.
            self.api.mark_delete(self.pins[self.gate][0])
        except (OSError, ValueError):
            raise StagingError("Native protected operation blocked; remnants remain HOLD") from None
        finally:
            self.active = False
            self._close(tuple(self.pins))  # No deletion disposition on failure.

    @_guarded
    def checked(self, path, directory):
        if not self.active or path not in self.pins:
            raise StagingError("unverified or inactive Native object; HOLD")
        handle, initial = self.pins[path]
        self._verify(self.api.info(handle), path, initial.acl, directory, initial.identity)
        return path

    @_guarded
    def create_staging(self, root, path):
        self.checkpoint()
        prefixes = (".review-staging-", ".review-restore-")
        prefix = next((value for value in prefixes if path.name.startswith(value)), None)
        if root not in (self.policy.primary, self.policy.backup) or path.parent != root or prefix is None:
            raise StagingError("unapproved Native staging name; HOLD")
        observation._event_id(path.name.removeprefix(prefix))
        handle = self.api.create(path, self.policy.staging_acl, directory=True,
                                 parent=self.pins[root][0])
        self._adopt(path, handle, self.policy.staging_acl, True)
        self.created_dirs.add(path)
        self.checkpoint()

    @_guarded
    def write_file(self, root, path, raw):
        if (root not in (self.policy.primary, self.policy.backup)
                or path.parent.parent != root or path.parent not in self.created_dirs
                or path.name not in {"a1_archive.zip", "observation.json", "index.json", "pending_review.json"}):
            raise StagingError("unapproved Native file name; HOLD")
        self.checkpoint()
        handle = self.api.create(path, self.policy.file_acl, parent=self.pins[path.parent][0])
        self._adopt(path, handle, self.policy.file_acl, False)
        self.checkpoint()  # Owner/SD/ID validated BEFORE any original/private byte.
        self.api.write(handle, raw)
        self.api.flush(handle)
        if self.api.read(handle, len(raw) + 1) != raw:
            raise StagingError("Native saved bytes mismatch; HOLD")
        self.checkpoint()

    @_guarded
    def read_copy(self, path, limit):
        self.checked(path, directory=False)
        raw = self.api.read(self.pins[path][0], limit)
        self.checked(path, directory=False)
        return raw


class NativeProtectedStore(ProtectedEvidenceStore):
    def __init__(self, root, boundary):
        super().__init__(root, None)
        self.boundary = boundary

    @property
    def _native_boundary(self):
        return self.boundary

    def _checked(self, path, *, directory):
        return self.boundary.checked(path, directory)

    def _create_staging(self, path):
        self.boundary.create_staging(self.root, path)

    def _write_file(self, path, raw):
        self.boundary.write_file(self.root, path, raw)

    def _read_copy(self, path, limit):
        return self.boundary.read_copy(path, limit)


def build_native_store(policy=None, *, api=None):
    _policy_valid(policy)  # Missing policy fails BEFORE loading any DLL.
    if api is None:
        from fr_b02b_windows_store import Win32StoreNative
        api = Win32StoreNative()  # Read-only by default; explicit capability required.
    return NativeStoreBoundary(policy, api).mirrored_store()
