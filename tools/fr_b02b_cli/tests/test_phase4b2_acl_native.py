"""ctypes ABI/failure tests. DLL functions are doubles, NEVER real Win32 calls."""

import ctypes as c
from ctypes import wintypes as w
import sys
import struct
import unittest
from unittest.mock import Mock, patch

from labs.phase4b2_acl import phase4b2_acl_lab as lab
from labs.phase4b2_acl import phase4b2_acl_native as adapter

SID = "S-1-5-21-100-200-300-1001"


class Dll:
    def __getattr__(self, name):
        value = Mock(return_value=1)
        setattr(self, name, value)
        return value


@unittest.skipUnless(sys.platform == "win32", "Windows ctypes ABI required")
class NativeContractTests(unittest.TestCase):
    def native(self, changes=True):
        dlls = tuple(Dll() for _ in range(4))
        with patch.object(c, "WinDLL", side_effect=AssertionError("real DLL forbidden")):
            native = adapter.Win32(allow_changes=changes, dlls=dlls)
        native.sid = SID
        native.k.LocalFree.return_value = None

        def convert(_text, _version, output, _size):
            c.cast(output, c.POINTER(c.c_void_p))[0] = 1234
            return True
        native.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = convert
        return native

    def metadata_prefix(self, native, handle):
        def information(_handle, output):
            c.cast(output, c.POINTER(adapter.FileInformation)).contents.links = 1
            return True

        def final(_handle, output, _length, _flags):
            output.value = "\\\\?\\" + handle.path
            return len(output.value)
        native.k.GetFileInformationByHandle.side_effect = information
        native.k.GetFinalPathNameByHandleW.side_effect = final

    def test_read_only_default_blocks_every_mutator_before_api(self):
        native = self.native(False)
        handle = adapter.Handle(10, native.full(lab.GATE), created=True)
        for action in (lambda: native.create_dir("", lab.ADMIN, lab.D_READ),
                       lambda: native.create_file(lab.GATE, SID, lab.F_RW_DELETE, gate=True),
                       lambda: native.write(handle, b"x"), lambda: native.flush(handle),
                       lambda: native.mark_delete(handle), lambda: native.terminate(handle)):
            with self.assertRaises(lab.Hold):
                action()
        for function in (native.k.CreateFileW, native.k.CreateDirectoryW, native.k.WriteFile,
                         native.k.SetFileInformationByHandle, native.k.TerminateProcess):
            function.assert_not_called()

    def test_create_new_collision_preserves_native_error_and_frees_descriptor(self):
        native = self.native()
        native.k.CreateFileW.return_value = c.c_void_p(-1).value
        for error in (5, 32, 80, 183, 112):
            with patch.object(c, "get_last_error", return_value=error):
                with self.assertRaises(lab.NativeFailure) as caught:
                    native.create_file(lab.GATE, SID, lab.F_RW_DELETE, gate=True)
            self.assertEqual(caught.exception.winerror, error)
        self.assertEqual(native.k.LocalFree.call_count, 5)
        args = native.k.CreateFileW.call_args.args
        self.assertEqual(args[1], 0xC0010000)  # GENERIC_READ|WRITE|DELETE
        self.assertEqual(args[2], 0)
        self.assertEqual(args[4], 1)  # CREATE_NEW
        self.assertFalse(args[5] & 0x04000000)  # no DELETE_ON_CLOSE
        native.k.SetFileInformationByHandle.assert_not_called()

    def test_descriptor_conversion_failure_creates_nothing(self):
        native = self.native()
        native.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = None
        native.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.return_value = False
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure):
                native.create_dir("", lab.ADMIN, lab.D_READ)
        native.k.CreateDirectoryW.assert_not_called()
        native.k.LocalFree.assert_not_called()

    def test_descriptor_release_failure_closes_created_handle_without_delete(self):
        native = self.native()
        native.k.CreateFileW.return_value = 99
        native.k.LocalFree.return_value = 1234
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure):
                native.create_file(lab.GATE, SID, lab.F_RW_DELETE, gate=True)
        native.k.CloseHandle.assert_called_once_with(99)
        native.k.SetFileInformationByHandle.assert_not_called()

    def test_disposition_uses_same_created_handle_and_one_byte_boolean(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.GATE), created=True)
        native.mark_delete(handle)
        args = native.k.SetFileInformationByHandle.call_args.args
        self.assertEqual((args[0], args[1], args[3]), (99, 4, 1))
        self.assertEqual(c.cast(args[2], c.POINTER(adapter.Disposition)).contents.delete, 1)
        native.k.SetFileInformationByHandle.reset_mock()
        with self.assertRaises(lab.Hold):
            native.mark_delete(adapter.Handle(99, handle.path))
        native.k.SetFileInformationByHandle.assert_not_called()
        self.assertEqual(c.sizeof(adapter.Disposition), 1)
        self.assertEqual(c.sizeof(adapter.FileIdentity), 24)
        self.assertEqual(c.sizeof(adapter.FileInformation), 52)
        self.assertEqual(c.sizeof(adapter.FindData), 592)
        self.assertEqual(c.sizeof(adapter.SecurityAttributes), 24 if c.sizeof(c.c_void_p) == 8 else 12)
        self.assertEqual(adapter.Rename.name.offset, 20 if c.sizeof(c.c_void_p) == 8 else 12)
        self.assertEqual(native.k.CreateFileW.restype, w.HANDLE)
        self.assertEqual(native.s.GetSecurityInfo.restype, w.DWORD)

    def test_rename_has_no_replace_utf16_length_and_terminator(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.IO), created=True)
        native.rename(handle, lab.RENAMED)
        args = native.k.SetFileInformationByHandle.call_args.args
        rename = c.cast(args[2], c.POINTER(adapter.Rename)).contents
        self.assertEqual(rename.flags, 0)
        self.assertIsNone(rename.root)
        self.assertEqual(rename.length, len(native.full(lab.RENAMED).encode("utf-16-le")))
        self.assertEqual(args[2].raw[-2:], b"\0\0")
        self.assertEqual(handle.path, native.full(lab.RENAMED))

    def test_security_dword_failure_does_not_use_last_error(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.GATE))
        self.metadata_prefix(native, handle)

        def security(_h, _type, _flags, _owner, _group, _dacl, _sacl, descriptor):
            c.cast(descriptor, c.POINTER(c.c_void_p))[0] = 1234
            return 5
        native.s.GetSecurityInfo.side_effect = security
        with patch.object(c, "get_last_error", return_value=32):
            with self.assertRaises(lab.NativeFailure) as caught:
                native.info(handle)
        self.assertEqual(caught.exception.winerror, 5)
        native.k.LocalFree.assert_called_once()

    def test_null_dacl_is_blocked_before_acl_dereference(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.GATE))
        self.metadata_prefix(native, handle)

        def security(_h, _type, _flags, owner, _group, _dacl, _sacl, descriptor):
            c.cast(descriptor, c.POINTER(c.c_void_p))[0] = 1234
            c.cast(owner, c.POINTER(c.c_void_p))[0] = 5678
            return 0

        def control(_sd, bits, _revision):
            c.cast(bits, c.POINTER(w.WORD))[0] = 0x1004
            return True
        native.s.GetSecurityInfo.side_effect = security
        native.s.GetSecurityDescriptorControl.side_effect = control
        with self.assertRaises(lab.Hold):
            native.info(handle)
        native.s.GetAclInformation.assert_not_called()
        native.k.LocalFree.assert_called_once()

    def test_partial_write_and_failed_close_are_not_retried(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.PARTIAL), created=True)
        with self.assertRaises(lab.Hold):
            native.write(handle, b"synthetic")  # fake reports zero bytes written
        native.k.WriteFile.assert_called_once()
        native.k.CloseHandle.return_value = False
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure):
                native.close(handle)
        native.close(handle)
        native.k.CloseHandle.assert_called_once()

    def test_successful_acl_parse_and_sid_allocations_are_released(self):
        native = self.native()
        handle = adapter.Handle(99, native.full(lab.GATE))
        self.metadata_prefix(native, handle)
        entries = lab.aces(SID, lab.F_RW_DELETE)
        chunks = []
        for _sid, mask, _flags, _kind in entries:
            # Minimal synthetic SID: revision=1, one subauthority, authority=5.
            sid_bytes = b"\1\1" + (5).to_bytes(6, "big") + (1).to_bytes(4, "little")
            chunks.append(struct.pack("<BBHI", 0, 0, 8 + len(sid_bytes), mask) + sid_bytes)
        size = 8 + sum(map(len, chunks))
        acl = c.create_string_buffer(struct.pack("<BBHHH", 2, 0, size, 3, 0) + b"".join(chunks))
        owner = c.create_string_buffer(b"synthetic-owner")
        sid_map = {c.addressof(owner): SID}
        pointers = []
        offset = 8
        for entry, chunk in zip(entries, chunks):
            pointers.append(c.addressof(acl) + offset)
            sid_map[c.addressof(acl) + offset + 8] = entry[0]
            offset += len(chunk)
        allocated = []

        def security(_h, _kind, _flags, result_owner, _group, result_dacl, _sacl, descriptor):
            for target, value in ((result_owner, c.addressof(owner)),
                                  (result_dacl, c.addressof(acl)), (descriptor, 1234)):
                c.cast(target, c.POINTER(c.c_void_p))[0] = value
            return 0

        def control(_sd, bits, _revision):
            c.cast(bits, c.POINTER(w.WORD))[0] = 0x1004
            return True

        def acl_size(_acl, output, _size, _kind):
            result = c.cast(output, c.POINTER(adapter.AclSize)).contents
            result.count, result.used = 3, size
            return True

        def get_ace(_acl, index, output):
            c.cast(output, c.POINTER(c.c_void_p))[0] = pointers[index]
            return True

        def sid_string(sid, output):
            buffer = c.create_unicode_buffer(sid_map[sid.value])
            allocated.append(buffer)
            c.cast(output, c.POINTER(c.c_void_p))[0] = c.addressof(buffer)
            return True
        native.s.GetSecurityInfo.side_effect = security
        native.s.GetSecurityDescriptorControl.side_effect = control
        native.s.GetAclInformation.side_effect = acl_size
        native.s.GetAce.side_effect = get_ace
        native.s.ConvertSidToStringSidW.side_effect = sid_string
        info = native.info(handle)
        lab.verify(info, SID, SID, lab.F_RW_DELETE, False)
        self.assertEqual(len(allocated), 4)
        self.assertEqual(native.k.LocalFree.call_count, 5)  # four SID texts + descriptor
        native.k.LocalFree.reset_mock()
        native.s.GetAce.return_value = False
        native.s.GetAce.side_effect = None
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure):
                native.info(handle)
        native.k.LocalFree.assert_called_once()

    def test_token_query_rejects_wrong_size_error_and_always_closes_token(self):
        native = self.native()

        def open_token(_process, _access, output):
            c.cast(output, c.POINTER(w.HANDLE))[0] = 88
            return True
        native.s.OpenProcessToken.side_effect = open_token
        native.s.GetTokenInformation.return_value = False
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure) as caught:
                native.token()
        self.assertEqual(caught.exception.winerror, 5)
        native.k.CloseHandle.assert_called_once()

    def test_success_with_null_security_descriptor_is_not_used_for_creation(self):
        native = self.native()
        native.s.ConvertStringSecurityDescriptorToSecurityDescriptorW.side_effect = None
        with self.assertRaises(lab.Hold):
            native.create_dir("", lab.ADMIN, lab.D_READ)
        native.k.CreateDirectoryW.assert_not_called()

    def test_process_wait_failure_is_distinct_from_timeout(self):
        native = self.native()
        handle = adapter.Handle(99)
        native.k.WaitForSingleObject.return_value = 0xFFFFFFFF
        with patch.object(c, "get_last_error", return_value=5):
            with self.assertRaises(lab.NativeFailure) as caught:
                native.terminate(handle)
        self.assertEqual(caught.exception.winerror, 5)
        native.k.WaitForSingleObject.return_value = 258
        with self.assertRaises(lab.Hold) as caught:
            native.terminate(handle)
        self.assertEqual(caught.exception.code, "TIMEOUT")

    def test_preflight_adapter_only_opens_existing_ancestors_for_read(self):
        native = self.native(False)
        native.token = Mock(return_value=lab.Token(SID, False, False))
        folder = c.create_unicode_buffer(r"C:\ProgramData")

        def known_folder(_guid, flags, _token, output):
            self.assertEqual(flags, 0)
            c.cast(output, c.POINTER(c.c_void_p))[0] = c.addressof(folder)
            return 0
        native.sh.SHGetKnownFolderPath.side_effect = known_folder
        native.info = Mock(return_value=lab.Info((1, "a" * 32), lab.ADMIN, (), True, False, 1))
        native.k.CreateFileW.side_effect = [11, 12]
        native.k.GetFileAttributesW.return_value = 0xFFFFFFFF
        with patch.object(c, "get_last_error", return_value=2):
            out = lab.Lab(native).preflight()
        self.assertEqual(out["status"], "PREFLIGHT_ONLY")
        self.assertFalse(native.allow_changes)
        native.token.assert_called_once()
        self.assertEqual(native.k.CreateFileW.call_count, 2)
        for call in native.k.CreateFileW.call_args_list:
            self.assertEqual(call.args[1], lab.READ_CONTROL | 0x80)
            self.assertEqual(call.args[4], 3)  # OPEN_EXISTING, never CREATE_NEW
            self.assertIsNone(call.args[3])   # no security descriptor supplied
        self.assertEqual(native.k.CloseHandle.call_count, 2)
        native.ole.CoTaskMemFree.assert_called_once()
        for function in (native.k.CreateDirectoryW, native.k.WriteFile, native.k.FlushFileBuffers,
                         native.k.SetFileInformationByHandle, native.k.OpenProcess,
                         native.k.TerminateProcess,
                         native.s.ConvertStringSecurityDescriptorToSecurityDescriptorW):
            function.assert_not_called()


if __name__ == "__main__":
    unittest.main()
