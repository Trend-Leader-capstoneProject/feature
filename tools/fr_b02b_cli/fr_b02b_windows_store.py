"""Win32/NT calls for the private store; import/construction never mutate objects.

Official contracts (unsupported APIs/options fail; no fallback):
https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntcreatefile
https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew
https://learn.microsoft.com/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo
https://learn.microsoft.com/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents
https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
"""

from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from uuid import UUID

from fr_b02b_native_store import AclPolicy, NativeError, ObjectInfo, VolumeInfo
from fr_b02b_windows_auth import get_current_process_sid


class UnicodeString(c.Structure):
    _fields_ = [("length", w.USHORT), ("maximum", w.USHORT), ("buffer", w.LPWSTR)]


class ObjectAttributes(c.Structure):
    _fields_ = [("length", w.ULONG), ("root", w.HANDLE),
                ("name", c.POINTER(UnicodeString)), ("attributes", w.ULONG),
                ("descriptor", c.c_void_p), ("quality", c.c_void_p)]


class IoStatus(c.Structure):
    # The NTSTATUS/PVOID union occupies one pointer; ULONG_PTR follows it.
    _fields_ = [("status_union", c.c_void_p), ("information", c.c_size_t)]


class SecurityAttributes(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


class FileId(c.Structure):
    _fields_ = [("volume", c.c_ulonglong), ("identifier", c.c_ubyte * 16)]


class FileInfo(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME),
                ("accessed", w.FILETIME), ("written", w.FILETIME),
                ("volume", w.DWORD), ("size_hi", w.DWORD), ("size_lo", w.DWORD),
                ("links", w.DWORD), ("index_hi", w.DWORD), ("index_lo", w.DWORD)]


class AclSize(c.Structure):
    _fields_ = [("count", w.DWORD), ("used", w.DWORD), ("free", w.DWORD)]


class AceHeader(c.Structure):
    _fields_ = [("kind", c.c_ubyte), ("flags", c.c_ubyte), ("size", w.WORD)]


class DiskExtent(c.Structure):
    _fields_ = [("disk", w.DWORD), ("offset", c.c_longlong), ("length", c.c_longlong)]


class DiskExtents(c.Structure):
    _fields_ = [("count", w.DWORD), ("extents", DiskExtent * 1)]


class Disposition(c.Structure):
    _fields_ = [("delete", c.c_ubyte)]  # BOOLEAN, not BOOL


@dataclass(repr=False)
class Handle:
    value: int
    path: Path
    kind: str = "existing"
    closed: bool = False


class Win32StoreNative:
    def __init__(self, *, allow_changes=False, dlls=None):
        if sys.platform != "win32":
            raise NativeError(50)
        self.allow_changes = allow_changes is True
        try:
            self.k, self.s, self.nt, self.sh, self.ole = dlls or tuple(
                c.WinDLL(name, use_last_error=True)
                for name in ("kernel32", "advapi32", "ntdll", "shell32", "ole32"))
        except (OSError, AttributeError):
            raise NativeError(50) from None
        ptr, pp = c.c_void_p, c.POINTER(c.c_void_p)
        self._bind(self.k, {
            "CreateFileW": ([w.LPCWSTR, w.DWORD, w.DWORD, ptr, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL), "LocalFree": ([ptr], ptr),
            "GetFileInformationByHandle": ([w.HANDLE, c.POINTER(FileInfo)], w.BOOL),
            "GetFileInformationByHandleEx": ([w.HANDLE, c.c_int, ptr, w.DWORD], w.BOOL),
            "GetFinalPathNameByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD),
            "GetVolumeInformationByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, ptr, ptr, ptr,
                                                w.LPWSTR, w.DWORD], w.BOOL),
            "DeviceIoControl": ([w.HANDLE, w.DWORD, ptr, w.DWORD, ptr, w.DWORD,
                                  c.POINTER(w.DWORD), ptr], w.BOOL),
            "WriteFile": ([w.HANDLE, ptr, w.DWORD, c.POINTER(w.DWORD), ptr], w.BOOL),
            "ReadFile": ([w.HANDLE, ptr, w.DWORD, c.POINTER(w.DWORD), ptr], w.BOOL),
            "FlushFileBuffers": ([w.HANDLE], w.BOOL),
            "SetFilePointerEx": ([w.HANDLE, c.c_longlong, ptr, w.DWORD], w.BOOL),
            "SetFileInformationByHandle": ([w.HANDLE, c.c_int, ptr, w.DWORD], w.BOOL),
        })
        self._bind(self.s, {
            "GetSecurityInfo": ([w.HANDLE, c.c_int, w.DWORD, pp, pp, pp, pp, pp], w.DWORD),
            "GetSecurityDescriptorControl": ([ptr, c.POINTER(w.WORD), c.POINTER(w.DWORD)], w.BOOL),
            "GetAclInformation": ([ptr, ptr, w.DWORD, c.c_int], w.BOOL),
            "GetAce": ([ptr, w.DWORD, pp], w.BOOL), "IsValidSid": ([ptr], w.BOOL),
            "ConvertSidToStringSidW": ([ptr, pp], w.BOOL),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                ([w.LPCWSTR, w.DWORD, pp, ptr], w.BOOL),
        })
        self._bind(self.nt, {
            "NtCreateFile": ([c.POINTER(w.HANDLE), w.DWORD, c.POINTER(ObjectAttributes),
                              c.POINTER(IoStatus), ptr, w.ULONG, w.ULONG, w.ULONG,
                              w.ULONG, ptr, w.ULONG], c.c_long),
            "RtlNtStatusToDosError": ([c.c_long], w.ULONG),
        })
        self._bind(self.sh, {"SHGetKnownFolderPath": ([ptr, w.DWORD, w.HANDLE, pp], c.c_long)})
        self._bind(self.ole, {"CoTaskMemFree": ([ptr], None)})

    @staticmethod
    def _bind(dll, functions):
        for name, (args, result) in functions.items():
            try:
                function = getattr(dll, name)
                function.argtypes, function.restype = args, result
            except AttributeError:
                raise NativeError(50) from None

    @staticmethod
    def _ok(value):
        if not value:
            raise NativeError(c.get_last_error())

    def _change(self):
        if not self.allow_changes:
            raise NativeError(5)

    @staticmethod
    def _live(handle):
        if handle.closed:
            raise NativeError(6)
        return handle.value

    def close(self, handle):
        if not handle.closed:
            handle.closed = True  # Uncertain close must not be retried.
            self._ok(self.k.CloseHandle(handle.value))

    def sid(self):
        return get_current_process_sid()  # TOKEN_QUERY only; no privilege adjustment.

    def known_folder(self):
        location = c.c_void_p()
        guid = c.create_string_buffer(UUID("62ab5d82-fdc1-4dc3-a9dd-070d1d495d97").bytes_le, 16)
        status = self.sh.SHGetKnownFolderPath(guid, 0, None, c.byref(location))
        try:
            if status or not location.value:
                raise NativeError(status & 0xFFFFFFFF)
            return Path(c.wstring_at(location))
        finally:
            if location.value:
                self.ole.CoTaskMemFree(location)

    def _open(self, path, access, share, directory=False, create=False, attributes=None):
        if create:
            self._change()
        flags = 0x00200000 | (0x02000000 if directory else 0x80)
        value = self.k.CreateFileW(str(path), access, share, attributes, 1 if create else 3, flags, None)
        if value in (None, 0, -1, c.c_void_p(-1).value):
            raise NativeError(c.get_last_error())
        return Handle(value, Path(path))

    def open_existing(self, path, directory, content=False):
        # Anchors opened component-by-component by the boundary and retained.
        access = 0x1200A1 if directory else (0x120089 if content else 0x120080)
        return self._open(path, access,
                          1 if content else 3, directory)

    @contextmanager
    def _descriptor(self, acl):
        if (acl.control != 0x1004 or not acl.aces
                or not re.fullmatch(r"S-1-(?:\d+-)+\d+", acl.owner)
                or any(kind not in (0, 1) or flags != 0 or not 0 < mask <= 0xFFFFFFFF
                       or not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid)
                       for kind, flags, mask, sid in acl.aces)):
            raise NativeError(1338)
        entries = "".join(f"({'A' if kind == 0 else 'D'};;0x{mask:08x};;;{sid})"
                          for kind, _flags, mask, sid in acl.aces)
        descriptor = c.c_void_p()
        self._ok(self.s.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            f"O:{acl.owner}D:P{entries}", 1, c.byref(descriptor), None))
        if not descriptor.value:
            raise NativeError(1338)
        try:
            yield descriptor
        finally:
            if self.k.LocalFree(descriptor):
                raise NativeError(c.get_last_error())

    def create(self, path, acl, directory=False, gate=False, parent=None):
        self._change()
        handle = None
        try:
            with self._descriptor(acl) as descriptor:
                if directory or not gate:
                    if (parent is None or Path(path).parent != parent.path
                            or (directory and not re.fullmatch(r"\.review-(?:staging|restore)-[A-Za-z0-9-]+", Path(path).name))
                            or (not directory and Path(path).name not in {
                                "a1_archive.zip", "observation.json", "index.json", "pending_review.json"})):
                        raise NativeError(87)
                    # Atomic directory creation returns the created handle. No
                    # CreateDirectoryW -> reopen window. Only documented flags:
                    # OBJ_CASE_INSENSITIVE, (NON_)DIRECTORY_FILE | SYNCHRONOUS_IO_NONALERT.
                    text = c.create_unicode_buffer(Path(path).name)
                    length = len(Path(path).name.encode("utf-16-le"))
                    name = UnicodeString(length, length + 2, c.cast(text, w.LPWSTR))
                    attributes = ObjectAttributes(c.sizeof(ObjectAttributes), self._live(parent),
                                                  c.pointer(name), 0x40, descriptor, None)
                    value, io = w.HANDLE(), IoStatus()
                    status = self.nt.NtCreateFile(
                        c.byref(value), 0x1200A1 if directory else 0x12019F, c.byref(attributes),
                        c.byref(io), None, 0x10 if directory else 0x80,
                        3 if directory else 0, 2, 0x21 if directory else 0x60, None, 0)
                    if status != 0:
                        raise NativeError(self.nt.RtlNtStatusToDosError(status))
                    if value.value:
                        handle = Handle(value.value, Path(path), "directory" if directory else "file")
                    if handle is None or io.information != 2 or io.status_union:
                        # FILE_CREATED + STATUS_SUCCESS, never opened/replaced.
                        raise NativeError(87)
                else:
                    if gate != (Path(path).name == "global.gate"):
                        raise NativeError(87)
                    attributes = SecurityAttributes(c.sizeof(SecurityAttributes), descriptor, False)
                    handle = self._open(path, 0xC0000000 | (0x10000 if gate else 0), 0,
                                        create=True, attributes=c.byref(attributes))
                    handle.kind = "gate" if gate else "file"
            return handle
        except BaseException:
            if handle is not None:
                self.close(handle)
            raise

    def _sid_text(self, sid):
        if not self.s.IsValidSid(sid):
            raise NativeError(1337)
        text = c.c_void_p()
        self._ok(self.s.ConvertSidToStringSidW(sid, c.byref(text)))
        if not text.value:
            raise NativeError(1337)
        try:
            return c.wstring_at(text)
        finally:
            if self.k.LocalFree(text):
                raise NativeError(c.get_last_error())

    def _acl(self, value):
        owner, dacl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
        status = self.s.GetSecurityInfo(value, 1, 5, c.byref(owner), None,
                                        c.byref(dacl), None, c.byref(descriptor))
        try:
            if status:
                raise NativeError(status)  # DWORD return, not GetLastError.
            if not owner.value or not dacl.value or not descriptor.value:
                raise NativeError(1338)
            control, revision = w.WORD(), w.DWORD()
            self._ok(self.s.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)))
            if not control.value & 4:
                raise NativeError(1338)
            size = AclSize()
            self._ok(self.s.GetAclInformation(dacl, c.byref(size), c.sizeof(size), 2))
            if not 0 < size.count <= 1024 or not 8 <= size.used <= 65535:
                raise NativeError(1338)
            entries = []
            for index in range(size.count):
                ace = c.c_void_p()
                self._ok(self.s.GetAce(dacl, index, c.byref(ace)))
                if (not ace.value or not dacl.value + 8 <= ace.value
                        <= dacl.value + size.used - c.sizeof(AceHeader)):
                    raise NativeError(1338)
                header = c.cast(ace, c.POINTER(AceHeader)).contents
                if (header.kind not in (0, 1) or header.size < 16
                        or ace.value + header.size > dacl.value + size.used):
                    raise NativeError(1338)
                count = c.c_ubyte.from_address(ace.value + 9).value
                if count > 15 or 16 + 4 * count > header.size:
                    raise NativeError(1338)
                entries.append((header.kind, header.flags, w.DWORD.from_address(ace.value + 4).value,
                                self._sid_text(c.c_void_p(ace.value + 8))))
            return AclPolicy(self._sid_text(owner), tuple(entries), control.value & 0x1504)
        finally:
            if descriptor.value and self.k.LocalFree(descriptor):
                raise NativeError(c.get_last_error())

    def _final_path(self, handle, flags=0):
        buffer = c.create_unicode_buffer(32768)
        count = self.k.GetFinalPathNameByHandleW(self._live(handle), buffer, len(buffer), flags)
        self._ok(count)
        if count >= len(buffer):
            raise NativeError(206)
        return buffer.value

    def info(self, handle):
        data, identity = FileInfo(), FileId()
        self._ok(self.k.GetFileInformationByHandle(self._live(handle), c.byref(data)))
        self._ok(self.k.GetFileInformationByHandleEx(self._live(handle), 18,
                                                    c.byref(identity), c.sizeof(identity)))
        final = self._final_path(handle)
        path = Path(final[4:] if final.startswith("\\\\?\\") else final)
        return ObjectInfo(path, (identity.volume, bytes(identity.identifier).hex()),
                          self._acl(self._live(handle)), bool(data.attributes & 0x10),
                          bool(data.attributes & 0x400), data.links)

    def volume(self, handle):
        fs = c.create_unicode_buffer(32)
        self._ok(self.k.GetVolumeInformationByHandleW(self._live(handle), None, 0,
                                                     None, None, None, fs, len(fs)))
        if fs.value != "NTFS":
            raise NativeError(50)
        final = self._final_path(handle, 1)  # VOLUME_NAME_GUID
        match = re.match(r"\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\", final)
        if not match:
            raise NativeError(50)
        guid = match.group().casefold()
        value = self.k.CreateFileW(guid[:-1], 0, 3, None, 3, 0, None)
        if value in (None, 0, -1, c.c_void_p(-1).value):
            raise NativeError(c.get_last_error())
        volume = Handle(value, Path(guid))
        try:
            capacity = 1
            while True:
                buffer = c.create_string_buffer(DiskExtents.extents.offset + capacity * c.sizeof(DiskExtent))
                returned = w.DWORD()
                ok = self.k.DeviceIoControl(value, 0x00560000, None, 0, buffer, len(buffer),
                                            c.byref(returned), None)
                error = c.get_last_error()
                if returned.value < DiskExtents.extents.offset or returned.value > len(buffer):
                    raise NativeError(error if not ok else 87)
                count = w.DWORD.from_buffer(buffer).value
                if not 0 < count <= 128:
                    raise NativeError(50)
                if not ok:
                    if error != 234 or count <= capacity:
                        raise NativeError(error)
                    capacity = count  # Bounded read-only buffer sizing, never a write retry.
                    continue
                required = DiskExtents.extents.offset + count * c.sizeof(DiskExtent)
                if count > capacity or returned.value < required:
                    raise NativeError(87)
                disks = set()
                for index in range(count):
                    extent = DiskExtent.from_buffer(buffer, DiskExtents.extents.offset + index * c.sizeof(DiskExtent))
                    if extent.offset < 0 or extent.length <= 0:
                        raise NativeError(87)
                    disks.add(extent.disk)
                identity = FileId()
                self._ok(self.k.GetFileInformationByHandleEx(self._live(handle), 18,
                                                            c.byref(identity), c.sizeof(identity)))
                return VolumeInfo(guid, identity.volume, tuple(sorted(disks)))
        finally:
            self.close(volume)

    def read(self, handle, limit):
        if not 0 < limit <= 20 * 1024 * 1024 + 1:
            raise NativeError(87)
        self._ok(self.k.SetFilePointerEx(self._live(handle), 0, None, 0))
        out = bytearray()
        while len(out) < limit:
            buffer = c.create_string_buffer(min(65536, limit - len(out)))
            count = w.DWORD()
            self._ok(self.k.ReadFile(self._live(handle), buffer, len(buffer), c.byref(count), None))
            if count.value > len(buffer):
                raise NativeError(87)
            if not count.value:
                break
            out.extend(buffer.raw[:count.value])
        return bytes(out)

    def write(self, handle, raw):
        self._change()
        if handle.kind != "file" or not isinstance(raw, bytes) or not 0 < len(raw) <= 20 * 1024 * 1024:
            raise NativeError(87)
        count = w.DWORD()
        self._ok(self.k.WriteFile(self._live(handle), raw, len(raw), c.byref(count), None))
        if count.value != len(raw):
            raise NativeError(112)  # Preserve short write; never retry it.

    def flush(self, handle):
        self._change()
        if handle.kind != "file":
            raise NativeError(87)
        self._ok(self.k.FlushFileBuffers(self._live(handle)))

    def mark_delete(self, handle):
        self._change()
        if handle.kind != "gate" or handle.path.name != "global.gate":
            raise NativeError(87)
        data = Disposition(1)
        self._ok(self.k.SetFileInformationByHandle(self._live(handle), 4, c.byref(data), c.sizeof(data)))
