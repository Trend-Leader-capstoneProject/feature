"""Windows ctypes ABI and DLL doubles only. NEVER real DLL calls."""

import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock, patch

import fr_b02b_native_store as boundary
import fr_b02b_windows_store as win

SID = "S-1-5-21-100-200-300-1001"


class Dll:
    def __getattr__(self, name):
        method = Mock(return_value=1)
        setattr(self, name, method)
        return method


@unittest.skipUnless(sys.platform == "win32", "Windows ABI required")
class WindowsStoreTests(unittest.TestCase):
    def setUp(self):
        self.acl = boundary.AclPolicy(SID, ((0, 0, 0x12019F, SID),), 0x1004)
        with patch.object(c, "WinDLL", side_effect=AssertionError("real DLL forbidden")):
            self.api = win.Win32StoreNative(allow_changes=True, dlls=tuple(Dll() for _ in range(5)))
        self.api.k.LocalFree.return_value = None
        self.path = Path(r"C:\synthetic-only\global.gate")

        def convert(_text, _revision, output, _size):
            c.cast(output, c.POINTER(c.c_void_p))[0] = 1234
            return True
        self.api.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = convert

    def test_read_only_capability_blocks_all_mutators_before_api(self):
        self.api.allow_changes = False
        gate = win.Handle(7, self.path, "gate")
        for action in (lambda: self.api.create(self.path, self.acl, gate=True),
                       lambda: self.api.create(self.path, self.acl, directory=True),
                       lambda: self.api.write(gate, b"x"), lambda: self.api.flush(gate),
                       lambda: self.api.mark_delete(gate)):
            with self.assertRaises(boundary.NativeError):
                action()
        self.api.k.CreateFileW.assert_not_called()
        self.api.nt.NtCreateFile.assert_not_called()
        self.api.k.WriteFile.assert_not_called()
        self.api.k.SetFileInformationByHandle.assert_not_called()

    def test_inventory_creation_cannot_fall_back_to_mutable_native_files(self):
        self.assertFalse(self.api.inventory_creation_available())
        with self.assertRaises(boundary.NativeError):
            self.api.create_inventory(self.path.with_name("inventory-LOCAL-OBS-test.json"), self.acl)
        self.api.k.CreateFileW.assert_not_called()
        self.api.nt.NtCreateFile.assert_not_called()
        self.api.k.WriteFile.assert_not_called()

    def test_gate_create_new_share_zero_and_failure_codes_preserved(self):
        self.api.k.CreateFileW.return_value = c.c_void_p(-1).value
        for code in (5, 32, 80, 183, 112):
            with patch.object(c, "get_last_error", return_value=code):
                with self.assertRaises(boundary.NativeError) as caught:
                    self.api.create(self.path, self.acl, gate=True)
            self.assertEqual(caught.exception.code, code)
        args = self.api.k.CreateFileW.call_args.args
        self.assertEqual((args[1], args[2], args[4]), (0xC0010000, 0, 1))
        self.assertFalse(args[5] & 0x04000000)  # No DELETE_ON_CLOSE
        self.assertEqual(self.api.k.LocalFree.call_count, 5)

    def test_atomic_relative_directory_creation_and_ntstatus_mapping(self):
        root = win.Handle(8, Path(r"C:\synthetic-only"))
        path = root.path / ".review-staging-LOCAL-OBS-test"

        def create(output, access, attributes, io, _size, _flags, share, disposition, options, _ea, _length):
            data = c.cast(attributes, c.POINTER(win.ObjectAttributes)).contents
            self.assertEqual(data.root, 8)
            self.assertEqual(data.name.contents.buffer, path.name)
            self.assertEqual(data.name.contents.length, len(path.name.encode("utf-16-le")))
            self.assertEqual((access, share, disposition, options, data.attributes),
                             (0x1200A1, 3, 2, 0x21, 0x40))
            self.assertTrue(data.descriptor)
            c.cast(output, c.POINTER(w.HANDLE))[0] = 9
            c.cast(io, c.POINTER(win.IoStatus)).contents.information = 2
            return 0
        self.api.nt.NtCreateFile.side_effect = create
        handle = self.api.create(path, self.acl, directory=True, parent=root)
        self.assertEqual((handle.value, handle.kind), (9, "directory"))
        self.api.k.CreateFileW.assert_not_called()
        self.api.nt.NtCreateFile.side_effect = None
        self.api.nt.NtCreateFile.return_value = -1073741771
        self.api.nt.RtlNtStatusToDosError.return_value = 80
        with self.assertRaises(boundary.NativeError) as caught:
            self.api.create(path, self.acl, directory=True, parent=root)
        self.assertEqual(caught.exception.code, 80)

    def test_new_original_file_uses_pinned_parent_handle_with_no_path_reopen(self):
        parent = win.Handle(8, Path(r"C:\synthetic-only\.review-staging-LOCAL-OBS-test"))
        path = parent.path / "index.json"

        def create(output, access, attributes, io, _size, flags, share, disposition, options, _ea, _length):
            data = c.cast(attributes, c.POINTER(win.ObjectAttributes)).contents
            self.assertEqual(data.root, 8)
            self.assertEqual(data.name.contents.buffer, "index.json")
            self.assertEqual((access, flags, share, disposition, options), (0x12019F, 0x80, 0, 2, 0x60))
            c.cast(output, c.POINTER(w.HANDLE))[0] = 9
            c.cast(io, c.POINTER(win.IoStatus)).contents.information = 2
            return 0
        self.api.nt.NtCreateFile.side_effect = create
        handle = self.api.create(path, self.acl, parent=parent)
        self.assertEqual(handle.kind, "file")
        self.api.k.CreateFileW.assert_not_called()
        self.api.k.WriteFile.assert_not_called()  # Creation never writes private bytes.

    def test_restore_directory_uses_relative_create_without_overwrite_or_fallback(self):
        parent = win.Handle(8, Path(r"C:\synthetic-only"))
        path = parent.path / ".review-restore-LOCAL-OBS-test"

        def create(output, access, attributes, io, _size, _flags, share, disposition, options, *_rest):
            data = c.cast(attributes, c.POINTER(win.ObjectAttributes)).contents
            self.assertEqual(data.root, 8)
            self.assertEqual(data.name.contents.buffer, path.name)
            self.assertEqual((share, disposition, options), (3, 2, 0x21))
            c.cast(output, c.POINTER(w.HANDLE))[0] = 9
            c.cast(io, c.POINTER(win.IoStatus)).contents.information = 2
            return 0

        self.api.nt.NtCreateFile.side_effect = create
        handle = self.api.create(path, self.acl, directory=True, parent=parent)
        self.assertEqual(handle.kind, "directory")
        self.api.k.CreateFileW.assert_not_called()

    def test_missing_native_symbol_has_no_fallback(self):
        with self.assertRaises(boundary.NativeError) as caught:
            win.Win32StoreNative._bind(object(), {"Missing": ([], w.BOOL)})
        self.assertEqual(caught.exception.code, 50)

    def test_nt_success_with_unexpected_open_result_closes_without_writing(self):
        parent = win.Handle(8, Path(r"C:\synthetic-only"))

        def wrong_result(output, _access, _attributes, io, *_rest):
            c.cast(output, c.POINTER(w.HANDLE))[0] = 77
            c.cast(io, c.POINTER(win.IoStatus)).contents.information = 1  # FILE_OPENED
            return 0
        self.api.nt.NtCreateFile.side_effect = wrong_result
        with self.assertRaises(boundary.NativeError):
            self.api.create(parent.path / "index.json", self.acl, parent=parent)
        self.api.k.CloseHandle.assert_called_once_with(77)
        self.api.k.WriteFile.assert_not_called()
        self.api.k.SetFileInformationByHandle.assert_not_called()

    def test_descriptor_failure_never_creates_or_writes_and_free_failure_closes(self):
        self.api.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = None
        with self.assertRaises(boundary.NativeError):
            self.api.create(self.path, self.acl, gate=True)  # success with NULL descriptor
        self.api.k.CreateFileW.assert_not_called()
        self.api.k.WriteFile.assert_not_called()
        self.api.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = (
            lambda _s, _v, out, _n: (setattr(c.cast(out, c.POINTER(c.c_void_p)).contents, "value", 1234) or 1))
        self.api.k.CreateFileW.return_value = 77
        self.api.k.LocalFree.return_value = 1234
        with self.assertRaises(boundary.NativeError):
            self.api.create(self.path, self.acl, gate=True)
        self.api.k.CloseHandle.assert_called_once_with(77)
        self.api.k.SetFileInformationByHandle.assert_not_called()

    def test_disposition_same_created_gate_only_and_natural_abi_alignment(self):
        gate = win.Handle(7, self.path, "gate")
        self.api.mark_delete(gate)
        args = self.api.k.SetFileInformationByHandle.call_args.args
        self.assertEqual((args[0], args[1], args[3]), (7, 4, 1))
        self.assertEqual(c.cast(args[2], c.POINTER(win.Disposition)).contents.delete, 1)
        self.api.k.SetFileInformationByHandle.reset_mock()
        with self.assertRaises(boundary.NativeError):
            self.api.mark_delete(win.Handle(7, self.path))
        self.api.k.SetFileInformationByHandle.assert_not_called()
        size64 = c.sizeof(c.c_void_p) == 8
        self.assertEqual(c.sizeof(win.ObjectAttributes), 48 if size64 else 24)
        self.assertEqual(c.sizeof(win.UnicodeString), 16 if size64 else 8)
        self.assertEqual(c.sizeof(win.IoStatus), 16 if size64 else 8)
        self.assertEqual(c.sizeof(win.FileId), 24)
        self.assertEqual(c.sizeof(win.FileInfo), 52)
        self.assertEqual(c.sizeof(win.DiskExtent), 24)
        self.assertEqual(win.DiskExtents.extents.offset, 8)
        self.assertEqual(self.api.nt.NtCreateFile.restype, c.c_long)
        self.assertEqual(self.api.s.GetSecurityInfo.restype, w.DWORD)

    def test_partial_write_and_close_failures_are_not_retried(self):
        handle = win.Handle(7, self.path.with_name("index.json"), "file")
        with self.assertRaises(boundary.NativeError):
            self.api.write(handle, b"synthetic")  # Fake reports zero bytes.
        self.api.k.WriteFile.assert_called_once()
        self.api.k.CloseHandle.return_value = False
        with self.assertRaises(boundary.NativeError):
            self.api.close(handle)
        self.api.close(handle)
        self.api.k.CloseHandle.assert_called_once()

    def test_existing_anchors_are_read_only_without_delete_sharing(self):
        self.api.k.CreateFileW.return_value = 9
        self.api.open_existing(self.path.parent, True)
        self.api.open_existing(self.path, False, True)
        for call in self.api.k.CreateFileW.call_args_list:
            args = call.args
            self.assertEqual(args[4], 3)
            self.assertFalse(args[1] & 0x400D0000)  # No write, DELETE, WRITE_DAC/OWNER
            self.assertFalse(args[2] & 4)
            self.assertTrue(args[5] & 0x00200000)
            self.assertIsNone(args[3])

    def test_gate_presence_query_never_opens_creates_or_modifies_it(self):
        self.api.allow_changes = False
        self.api.k.GetFileAttributesW.return_value = 0x400  # Reparse object also counts as present.
        self.assertTrue(self.api.exists(self.path))
        self.api.k.GetFileAttributesW.return_value = 0xFFFFFFFF
        for code in (2, 3, 5, 32):
            with patch.object(c, "get_last_error", return_value=code):
                if code in (2, 3):
                    self.assertFalse(self.api.exists(self.path))
                else:
                    with self.assertRaises(boundary.NativeError) as caught:
                        self.api.exists(self.path)
                    self.assertEqual(caught.exception.code, code)
        self.api.k.CreateFileW.assert_not_called()
        self.api.nt.NtCreateFile.assert_not_called()
        self.api.k.SetFileInformationByHandle.assert_not_called()

    def test_readonly_directory_listing_closes_search_handle_and_no_file_io(self):
        self.api.allow_changes = False
        handle = win.Handle(7, self.path.parent)
        self.api.info = Mock(return_value=boundary.ObjectInfo(handle.path, (1, "a" * 32),
                                                             self.acl, True, False, 1))

        def first(_path, output):
            c.cast(output, c.POINTER(win.FindData)).contents.name = "."
            return 77

        names = iter(("..", "synthetic-child"))

        def following(_handle, output):
            try:
                c.cast(output, c.POINTER(win.FindData)).contents.name = next(names)
                return 1
            except StopIteration:
                c.set_last_error(18)
                return 0

        self.api.k.FindFirstFileW.side_effect = first
        self.api.k.FindNextFileW.side_effect = following
        self.assertEqual(self.api.children(handle), ("synthetic-child",))
        self.api.k.FindClose.assert_called_once_with(77)
        self.api.k.CloseHandle.assert_not_called()
        self.api.k.CreateFileW.assert_not_called()
        self.api.k.ReadFile.assert_not_called()
        self.api.k.WriteFile.assert_not_called()
        self.assertEqual(c.sizeof(win.FindData), 592)
        self.assertEqual(self.api.k.FindFirstFileW.restype, w.HANDLE)

    def test_directory_listing_failure_and_reparse_child_are_not_empty_success(self):
        handle = win.Handle(7, self.path.parent)
        self.api.info = Mock(return_value=boundary.ObjectInfo(handle.path, (1, "a" * 32),
                                                             self.acl, True, False, 1))
        self.api.k.FindFirstFileW.return_value = c.c_void_p(-1).value
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(boundary.NativeError) as caught:
                self.api.children(handle)
        self.assertEqual(caught.exception.code, 5)

        def reparse(_path, output):
            data = c.cast(output, c.POINTER(win.FindData)).contents
            data.name, data.attributes = "reparse-child", 0x400
            return 77

        self.api.k.FindFirstFileW.side_effect = reparse
        with self.assertRaises(boundary.NativeError):
            self.api.children(handle)
        self.api.k.FindClose.assert_called_once_with(77)

    def test_security_error_uses_dword_and_null_dacl_is_never_dereferenced(self):
        self.api.s.GetSecurityInfo.return_value = 5
        with patch.object(c, "get_last_error", return_value=32):
            with self.assertRaises(boundary.NativeError) as caught:
                self.api._acl(7)
        self.assertEqual(caught.exception.code, 5)
        self.api.s.GetSecurityInfo.return_value = 0
        with self.assertRaises(boundary.NativeError):
            self.api._acl(7)
        self.api.s.GetAclInformation.assert_not_called()

    def volume_fixture(self):
        guid = "\\\\?\\Volume{00000000-0000-0000-0000-000000000001}\\"
        self.api._final_path = Mock(return_value=guid + "synthetic-only")

        def fs(_h, _n, _ns, _v, _m, _f, output, _size):
            output.value = "NTFS"
            return 1
        self.api.k.GetVolumeInformationByHandleW.side_effect = fs
        self.api.k.CreateFileW.return_value = 99
        return win.Handle(7, self.path.parent)

    def test_ace_order_deny_masks_and_owner_parse_release_all_native_allocations(self):
        entries = ((1, 0, 2, SID), (0, 0, 0x120089, SID))
        sid_bytes = b"\1\1" + (5).to_bytes(6, "big") + (1).to_bytes(4, "little")
        chunks = [struct.pack("<BBHI", kind, flags, 8 + len(sid_bytes), mask) + sid_bytes
                  for kind, flags, mask, _ in entries]
        size = 8 + sum(map(len, chunks))
        acl = c.create_string_buffer(struct.pack("<BBHHH", 2, 0, size, 2, 0) + b"".join(chunks))
        owner = c.create_string_buffer(sid_bytes)
        allocated = []

        def security(_h, _kind, _flags, result_owner, _group, result_dacl, _sacl, descriptor):
            for target, value in ((result_owner, c.addressof(owner)),
                                  (result_dacl, c.addressof(acl)), (descriptor, 1234)):
                c.cast(target, c.POINTER(c.c_void_p))[0] = value
            return 0

        def control(_descriptor, output, _revision):
            c.cast(output, c.POINTER(w.WORD))[0] = 0x1004
            return 1

        def acl_size(_acl, output, _length, _kind):
            data = c.cast(output, c.POINTER(win.AclSize)).contents
            data.count, data.used = 2, size
            return 1

        def ace(_acl, index, output):
            c.cast(output, c.POINTER(c.c_void_p))[0] = c.addressof(acl) + 8 + index * len(chunks[0])
            return 1

        def sid(_sid, output):
            value = c.create_unicode_buffer(SID)
            allocated.append(value)
            c.cast(output, c.POINTER(c.c_void_p))[0] = c.addressof(value)
            return 1
        self.api.s.GetSecurityInfo.side_effect = security
        self.api.s.GetSecurityDescriptorControl.side_effect = control
        self.api.s.GetAclInformation.side_effect = acl_size
        self.api.s.GetAce.side_effect = ace
        self.api.s.ConvertSidToStringSidW.side_effect = sid
        self.assertEqual(self.api._acl(7), boundary.AclPolicy(SID, entries, 0x1004))
        self.assertEqual(self.api.k.LocalFree.call_count, 4)  # 3 SID strings + descriptor
        self.api.k.LocalFree.reset_mock()
        win.AceHeader.from_buffer(acl, 8).kind = 5  # Unsupported object ACE.
        with self.assertRaises(boundary.NativeError):
            self.api._acl(7)
        self.api.k.LocalFree.assert_called_once()

    def test_volume_extents_resizes_read_buffer_and_closes_volume(self):
        handle = self.volume_fixture()
        calls = []

        def ioctl(_h, code, _in, _insize, output, size, returned, _overlapped):
            self.assertEqual(code, 0x00560000)
            calls.append(size)
            w.DWORD.from_buffer(output).value = 2
            c.cast(returned, c.POINTER(w.DWORD))[0] = size
            if len(calls) == 1:
                c.set_last_error(234)
                return 0
            for i in range(2):
                extent = win.DiskExtent.from_buffer(output, 8 + i * 24)
                extent.disk, extent.offset, extent.length = i + 1, 0, 4096
            return 1
        self.api.k.DeviceIoControl.side_effect = ioctl
        volume = self.api.volume(handle)
        self.assertEqual(calls, [32, 56])
        self.assertEqual(volume.disks, (1, 2))
        self.api.k.CloseHandle.assert_called_once_with(99)

    def test_volume_query_failure_does_not_guess_or_leak_handle(self):
        handle = self.volume_fixture()
        self.api.k.DeviceIoControl.return_value = 0
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(boundary.NativeError) as caught:
                self.api.volume(handle)
        self.assertEqual(caught.exception.code, 5)
        self.api.k.CloseHandle.assert_called_once_with(99)

    def test_read_uses_same_handle_and_bounded_chunks(self):
        handle = win.Handle(7, self.path)

        def read(value, output, size, count, _overlapped):
            self.assertEqual(value, 7)
            c.memmove(output, b"abc", 3)
            c.cast(count, c.POINTER(w.DWORD))[0] = 3
            return 1
        self.api.k.ReadFile.side_effect = read
        self.assertEqual(self.api.read(handle, 3), b"abc")
        self.api.k.CreateFileW.assert_not_called()
        self.api.k.SetFilePointerEx.assert_called_once_with(7, 0, None, 0)


if __name__ == "__main__":
    unittest.main()
