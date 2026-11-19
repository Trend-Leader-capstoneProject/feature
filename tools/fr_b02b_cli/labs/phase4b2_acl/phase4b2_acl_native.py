"""Win32 adapter for the fixed synthetic lab, never the operational CLI.

Construction/import performs no mutation. allow_changes defaults to False.
Contracts and unexecuted Windows checks: ../../docs/phase4b2/phase4b2_acl_harness_review.md.
"""

from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
from pathlib import PureWindowsPath
import re
import sys
from uuid import UUID

if __package__:
    from . import phase4b2_acl_lab as lab
else:
    import phase4b2_acl_lab as lab


class SecurityAttributes(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


class FileIdentity(c.Structure):
    _fields_ = [("volume", c.c_ulonglong), ("file_id", c.c_ubyte * 16)]


class FileInformation(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME),
                ("accessed", w.FILETIME), ("written", w.FILETIME),
                ("volume", w.DWORD), ("size_hi", w.DWORD), ("size_lo", w.DWORD),
                ("links", w.DWORD), ("index_hi", w.DWORD), ("index_lo", w.DWORD)]


class AclSize(c.Structure):
    _fields_ = [("count", w.DWORD), ("used", w.DWORD), ("free", w.DWORD)]


class AceHeader(c.Structure):
    _fields_ = [("kind", c.c_ubyte), ("flags", c.c_ubyte), ("size", w.WORD)]


class Disposition(c.Structure):
    _fields_ = [("delete", c.c_ubyte)]  # BOOLEAN, not BOOL.


class Rename(c.Structure):
    # DWORD-sized union (Flags/BOOLEAN ReplaceIfExists), natural HANDLE alignment.
    _fields_ = [("flags", w.DWORD), ("root", w.HANDLE), ("length", w.DWORD),
                ("name", w.WCHAR * 1)]


class FindData(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME),
                ("accessed", w.FILETIME), ("written", w.FILETIME),
                ("size_hi", w.DWORD), ("size_lo", w.DWORD),
                ("reserved0", w.DWORD), ("reserved1", w.DWORD),
                ("name", w.WCHAR * 260), ("alternate", w.WCHAR * 14)]


@dataclass(repr=False)
class Handle:
    value: int
    path: str = ""
    closed: bool = False
    created: bool = False


class Win32:
    def __init__(self, *, allow_changes=False, dlls=None):
        if sys.platform != "win32":
            raise lab.Hold("UNSUPPORTED")
        self.allow_changes, self.sid = allow_changes is True, None
        self.k, self.s, self.sh, self.ole = dlls or tuple(
            c.WinDLL(name, use_last_error=True)
            for name in ("kernel32", "advapi32", "shell32", "ole32"))
        ptr, pp = c.c_void_p, c.POINTER(c.c_void_p)
        self._bind(self.k, {
            "CreateFileW": ([w.LPCWSTR, w.DWORD, w.DWORD, ptr, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
            "CreateDirectoryW": ([w.LPCWSTR, ptr], w.BOOL),
            "GetFileAttributesW": ([w.LPCWSTR], w.DWORD),
            "CloseHandle": ([w.HANDLE], w.BOOL), "LocalFree": ([ptr], ptr),
            "GetFileInformationByHandle": ([w.HANDLE, c.POINTER(FileInformation)], w.BOOL),
            "GetFileInformationByHandleEx": ([w.HANDLE, c.c_int, ptr, w.DWORD], w.BOOL),
            "GetFinalPathNameByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD),
            "SetFileInformationByHandle": ([w.HANDLE, c.c_int, ptr, w.DWORD], w.BOOL),
            "WriteFile": ([w.HANDLE, ptr, w.DWORD, c.POINTER(w.DWORD), ptr], w.BOOL),
            "ReadFile": ([w.HANDLE, ptr, w.DWORD, c.POINTER(w.DWORD), ptr], w.BOOL),
            "FlushFileBuffers": ([w.HANDLE], w.BOOL),
            "SetFilePointerEx": ([w.HANDLE, c.c_longlong, ptr, w.DWORD], w.BOOL),
            "FindFirstFileW": ([w.LPCWSTR, c.POINTER(FindData)], w.HANDLE),
            "FindNextFileW": ([w.HANDLE, c.POINTER(FindData)], w.BOOL),
            "FindClose": ([w.HANDLE], w.BOOL),
            "GetCurrentProcess": ([], w.HANDLE),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "GetProcessTimes": ([w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME),
                                 c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)], w.BOOL),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        })
        self._bind(self.s, {
            "GetSecurityInfo": ([w.HANDLE, c.c_int, w.DWORD, pp, pp, pp, pp, pp], w.DWORD),
            "GetSecurityDescriptorControl": ([ptr, c.POINTER(w.WORD), c.POINTER(w.DWORD)], w.BOOL),
            "GetAclInformation": ([ptr, ptr, w.DWORD, c.c_int], w.BOOL),
            "GetAce": ([ptr, w.DWORD, pp], w.BOOL),
            "IsValidSid": ([ptr], w.BOOL),
            "ConvertSidToStringSidW": ([ptr, pp], w.BOOL),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                ([w.LPCWSTR, w.DWORD, pp, c.POINTER(w.DWORD)], w.BOOL),
            "OpenProcessToken": ([w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL),
            "GetTokenInformation": ([w.HANDLE, c.c_int, ptr, w.DWORD, c.POINTER(w.DWORD)], w.BOOL),
            "LookupPrivilegeNameW": ([w.LPCWSTR, ptr, w.LPWSTR, c.POINTER(w.DWORD)], w.BOOL),
        })
        self._bind(self.sh, {"SHGetKnownFolderPath": ([ptr, w.DWORD, w.HANDLE, pp], c.c_long)})
        self._bind(self.ole, {"CoTaskMemFree": ([ptr], None)})

    @staticmethod
    def _bind(dll, functions):
        for name, (arguments, result) in functions.items():
            function = getattr(dll, name)
            function.argtypes, function.restype = arguments, result

    @staticmethod
    def _ok(value):
        if not value:
            raise lab.NativeFailure(c.get_last_error())

    def _change(self):
        if not self.allow_changes:
            raise lab.Hold("EXECUTION_NOT_APPROVED")

    @staticmethod
    def full(name):
        if name not in lab.NAMES:
            raise lab.Hold("PATH_NOT_APPROVED")
        return lab.ROOT + ("\\" + name if name else "")

    def _policy(self, name, owner, mask):
        expected = ((lab.ADMIN, lab.DIRS[name]) if name in lab.DIRS else
                    (lab.ADMIN, lab.F_READ) if name in (*lab.CONFIG, lab.INVENTORY) else
                    (self.sid, lab.D_READ | 6 | lab.DELETE) if name in lab.WORK_DIRS else
                    (self.sid, lab.F_RW_DELETE) if name in (lab.GATE, lab.IO, lab.RENAMED) else
                    (self.sid, lab.F_RW))
        if not self.sid or (owner, mask) != expected:
            raise lab.Hold("ACL_MISMATCH")

    @contextmanager
    def _attributes(self, owner, mask):
        if not all(re.fullmatch(r"S-1-(?:\d+-)+\d+", sid or "") for sid in (owner, self.sid)):
            raise lab.Hold("IDENTITY_MISMATCH")
        sddl = f"O:{owner}D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x{mask:08x};;;{self.sid})"
        descriptor = c.c_void_p()
        self._ok(self.s.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, c.byref(descriptor), None))
        if not descriptor.value:
            raise lab.Hold("ACL_MISMATCH")
        try:
            yield SecurityAttributes(c.sizeof(SecurityAttributes), descriptor, False)
        finally:
            if self.k.LocalFree(descriptor):
                raise lab.NativeFailure(c.get_last_error())

    def close(self, handle):
        if not handle.closed:
            handle.closed = True  # Do not retry an uncertain/double-close.
            self._ok(self.k.CloseHandle(handle.value))

    @staticmethod
    def _live(handle):
        if handle.closed:
            raise lab.Hold("IDENTITY_MISMATCH")
        return handle.value

    def _open(self, path, access, directory, share, disposition=3, attributes=None):
        if disposition != 3:
            self._change()
        flags = 0x00200000 | (0x02000000 if directory else 0x80)
        value = self.k.CreateFileW(path, access, share, attributes, disposition, flags, None)
        if value in (None, 0, -1, c.c_void_p(-1).value):
            raise lab.NativeFailure(c.get_last_error())
        return Handle(value, path)

    def open(self, name, access, directory, share):
        return self._open(self.full(name), access, directory, share)

    def exists(self, name):
        flags = self.k.GetFileAttributesW(self.full(name))
        if flags == 0xFFFFFFFF:
            code = c.get_last_error()
            if code in (2, 3):
                return False
            raise lab.NativeFailure(code)
        if flags & 0x400:
            raise lab.Hold("OBJECT_MISMATCH")
        return True

    @contextmanager
    def parents(self):
        location = c.c_void_p()
        guid = c.create_string_buffer(UUID("62ab5d82-fdc1-4dc3-a9dd-070d1d495d97").bytes_le, 16)
        hr = self.sh.SHGetKnownFolderPath(guid, 0, None, c.byref(location))
        if hr != 0:
            raise lab.NativeFailure(hr & 0xFFFFFFFF)
        if not location.value:
            raise lab.Hold("PATH_NOT_APPROVED")
        try:
            folder = c.wstring_at(location)
        finally:
            self.ole.CoTaskMemFree(location)
        if folder.casefold() != "c:\\programdata":
            raise lab.Hold("PATH_NOT_APPROVED")
        handles = []
        try:
            for path in ("C:\\", folder):
                handle = self._open(path, lab.READ_CONTROL | 0x80, True, 3)
                handles.append(handle)
                info = self.info(handle)
                if not info.directory or info.reparse:
                    raise lab.Hold("OBJECT_MISMATCH")
            yield
        finally:
            # Attempt all releases even if one CloseHandle fails.
            failure = None
            for handle in reversed(handles):
                try:
                    self.close(handle)
                except lab.NativeFailure as error:
                    failure = error
            if failure:
                raise failure

    def create_dir(self, name, owner, mask):
        self._change()
        if name not in lab.DIRS and name not in lab.WORK_DIRS:
            raise lab.Hold("PATH_NOT_APPROVED")
        path = self.full(name)
        self._policy(name, owner, mask)
        with self._attributes(owner, mask) as attributes:
            self._ok(self.k.CreateDirectoryW(path, c.byref(attributes)))

    def create_file(self, name, owner, mask, gate=False):
        self._change()
        path = self.full(name)
        self._policy(name, owner, mask)
        if name in lab.DIRS or name in lab.WORK_DIRS or gate != (name == lab.GATE):
            raise lab.Hold("PATH_NOT_APPROVED")
        access = 0x80000000 | 0x40000000 | (lab.DELETE if mask & lab.DELETE else 0)
        handle = None
        try:
            with self._attributes(owner, mask) as attributes:
                handle = self._open(path, access, False, 0, 1, c.byref(attributes))
                handle.created = True
            return handle
        except BaseException:
            if handle is not None:
                self.close(handle)
            raise

    def _sid_text(self, sid):
        if not self.s.IsValidSid(sid):
            raise lab.Hold("IDENTITY_MISMATCH")
        text = c.c_void_p()
        self._ok(self.s.ConvertSidToStringSidW(sid, c.byref(text)))
        if not text.value:
            raise lab.Hold("IDENTITY_MISMATCH")
        try:
            return c.wstring_at(text)
        finally:
            if self.k.LocalFree(text):
                raise lab.NativeFailure(c.get_last_error())

    def info(self, handle):
        value = self._live(handle)
        data, identity = FileInformation(), FileIdentity()
        self._ok(self.k.GetFileInformationByHandle(value, c.byref(data)))
        self._ok(self.k.GetFileInformationByHandleEx(value, 18, c.byref(identity), c.sizeof(identity)))
        path = c.create_unicode_buffer(32768)
        count = self.k.GetFinalPathNameByHandleW(value, path, len(path), 0)
        self._ok(count)
        if count >= len(path):
            raise lab.Hold("PATH_NOT_APPROVED")
        final = path.value[4:] if path.value.startswith("\\\\?\\") else path.value
        if PureWindowsPath(final) != PureWindowsPath(handle.path) or data.attributes & 0x400:
            raise lab.Hold("OBJECT_MISMATCH")
        owner, dacl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
        status = self.s.GetSecurityInfo(value, 1, 0x5, c.byref(owner), None,
                                        c.byref(dacl), None, c.byref(descriptor))
        try:
            if status:
                raise lab.NativeFailure(status)  # DWORD error, not GetLastError.
            if not descriptor.value:
                raise lab.Hold("ACL_MISMATCH")
            control, revision = w.WORD(), w.DWORD()
            self._ok(self.s.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)))
            if not owner.value or not dacl.value or not control.value & 4:
                raise lab.Hold("ACL_MISMATCH")
            size = AclSize()
            self._ok(self.s.GetAclInformation(dacl, c.byref(size), c.sizeof(size), 2))
            entries = []
            if not 0 < size.count <= 128 or not 8 <= size.used <= 65535:
                raise lab.Hold("ACL_MISMATCH")
            for index in range(size.count):
                ace = c.c_void_p()
                self._ok(self.s.GetAce(dacl, index, c.byref(ace)))
                if not ace.value:
                    raise lab.Hold("ACL_MISMATCH")
                if not dacl.value + 8 <= ace.value <= dacl.value + size.used - c.sizeof(AceHeader):
                    raise lab.Hold("ACL_MISMATCH")
                header = c.cast(ace, c.POINTER(AceHeader)).contents
                if header.kind != 0 or header.size < 16 or ace.value + header.size > dacl.value + size.used:
                    raise lab.Hold("ACL_MISMATCH")  # No guess for unsupported ACE.
                subcount = c.c_ubyte.from_address(ace.value + 9).value
                if subcount > 15 or 16 + 4 * subcount > header.size:
                    raise lab.Hold("ACL_MISMATCH")
                sid = self._sid_text(c.c_void_p(ace.value + 8))
                mask = w.DWORD.from_address(ace.value + 4).value
                entries.append((sid, mask, header.flags, header.kind))
            return lab.Info((identity.volume, bytes(identity.file_id).hex()),
                            self._sid_text(owner), tuple(sorted(entries)),
                            bool(data.attributes & 0x10), False, data.links,
                            bool(control.value & 0x1000))
        finally:
            if descriptor.value and self.k.LocalFree(descriptor):
                raise lab.NativeFailure(c.get_last_error())

    def children(self, name):
        with lab.opened(self, name, directory=True, share=3) as directory:
            if not self.info(directory).directory:
                raise lab.Hold("OBJECT_MISMATCH")
            data = FindData()
            found = self.k.FindFirstFileW(self.full(name) + "\\*", c.byref(data))
            if found in (None, 0, -1, c.c_void_p(-1).value):
                if c.get_last_error() == 2:
                    return []
                raise lab.NativeFailure(c.get_last_error())
            try:
                names = []
                while True:
                    if data.name not in (".", ".."):
                        if data.attributes & 0x400:
                            raise lab.Hold("OBJECT_MISMATCH")
                        names.append(data.name)
                    if not self.k.FindNextFileW(found, c.byref(data)):
                        if c.get_last_error() != 18:
                            raise lab.NativeFailure(c.get_last_error())
                        return names
            finally:
                self._ok(self.k.FindClose(found))

    def write(self, handle, payload):
        self._change()
        if not handle.created:
            raise lab.Hold("IDENTITY_MISMATCH")
        if not isinstance(payload, bytes) or not 0 < len(payload) <= 65536:
            raise lab.Hold("OBJECT_MISMATCH")
        written = w.DWORD()
        self._ok(self.k.WriteFile(self._live(handle), payload, len(payload), c.byref(written), None))
        if written.value != len(payload):
            raise lab.Hold("OBJECT_MISMATCH")  # Partial write remains HOLD.

    def flush(self, handle):
        self._change()
        if not handle.created:
            raise lab.Hold("IDENTITY_MISMATCH")
        self._ok(self.k.FlushFileBuffers(self._live(handle)))

    def read(self, handle):
        value = self._live(handle)
        self._ok(self.k.SetFilePointerEx(value, 0, None, 0))
        out = bytearray()
        while True:
            buffer, count = c.create_string_buffer(4096), w.DWORD()
            self._ok(self.k.ReadFile(value, buffer, len(buffer), c.byref(count), None))
            if count.value > len(buffer) or len(out) + count.value > 65536:
                raise lab.Hold("OBJECT_MISMATCH")
            if not count.value:
                return bytes(out)
            out.extend(buffer.raw[:count.value])

    def rename(self, handle, destination):
        self._change()
        if not handle.created or handle.path != self.full(lab.IO) or destination != lab.RENAMED:
            raise lab.Hold("PATH_NOT_APPROVED")
        path = self.full(destination)
        name = path.encode("utf-16-le")
        buffer = c.create_string_buffer(Rename.name.offset + len(name) + 2)
        data = c.cast(buffer, c.POINTER(Rename)).contents
        data.flags, data.root, data.length = 0, None, len(name)
        c.memmove(c.addressof(buffer) + Rename.name.offset, name, len(name))
        self._ok(self.k.SetFileInformationByHandle(self._live(handle), 3, buffer, len(buffer)))
        handle.path = path

    def mark_delete(self, handle):
        self._change()
        if not handle.created or handle.path != self.full(lab.GATE):
            raise lab.Hold("PATH_NOT_APPROVED")
        data = Disposition(1)
        self._ok(self.k.SetFileInformationByHandle(self._live(handle), 4, c.byref(data), c.sizeof(data)))

    def _query(self, token, kind, fixed=None):
        needed = w.DWORD()
        if fixed is None:
            ok = self.s.GetTokenInformation(token, kind, None, 0, c.byref(needed))
            code = c.get_last_error()
            if ok or code != 122 or not 0 < needed.value <= 65536:
                raise lab.NativeFailure(code)
            fixed = needed.value
        buffer = c.create_string_buffer(fixed)
        self._ok(self.s.GetTokenInformation(token, kind, buffer, len(buffer), c.byref(needed)))
        if not 0 < needed.value <= len(buffer) or (kind == 20 and needed.value != 4):
            raise lab.Hold("OBJECT_MISMATCH")
        return buffer

    def token(self):
        token = w.HANDLE()
        self._ok(self.s.OpenProcessToken(self.k.GetCurrentProcess(), 8, c.byref(token)))
        try:
            user = self._query(token, 1)
            if len(user) < c.sizeof(c.c_void_p) + 4:
                raise lab.Hold("IDENTITY_MISMATCH")
            sid = self._sid_text(c.c_void_p.from_buffer(user))
            self.sid = sid
            elevated = bool(w.DWORD.from_buffer(self._query(token, 20, 4)).value)
            privileges = self._query(token, 3)
            if len(privileges) < 4:
                raise lab.Hold("IDENTITY_MISMATCH")
            count = w.DWORD.from_buffer(privileges).value
            if 4 + count * 12 > len(privileges):
                raise lab.Hold("IDENTITY_MISMATCH")
            dangerous = False
            for index in range(count):
                offset = 4 + index * 12
                if not w.DWORD.from_buffer(privileges, offset + 8).value & 2:
                    continue
                luid, size = c.byref(privileges, offset), w.DWORD(256)
                name = c.create_unicode_buffer(256)
                self._ok(self.s.LookupPrivilegeNameW(None, luid, name, c.byref(size)))
                dangerous |= name.value in ("SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege")
            return lab.Token(sid, elevated, dangerous)
        finally:
            self._ok(self.k.CloseHandle(token))

    def process_handle(self, pid):
        self._change()
        value = self.k.OpenProcess(0x1000 | 0x100000 | 1, False, pid)
        self._ok(value)
        return Handle(value)

    def process_created(self, handle):
        times = [w.FILETIME() for _ in range(4)]
        self._ok(self.k.GetProcessTimes(self._live(handle), *(c.byref(t) for t in times)))
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        if not created:
            raise lab.Hold("IDENTITY_MISMATCH")
        return created

    def terminate(self, handle):
        self._change()
        self._ok(self.k.TerminateProcess(self._live(handle), 97))
        status = self.k.WaitForSingleObject(self._live(handle), 5000)
        if status == 0xFFFFFFFF:
            raise lab.NativeFailure(c.get_last_error())
        if status == 258:
            raise lab.Hold("TIMEOUT")
        if status != 0:
            raise lab.Hold("CHILD_FAILURE")
