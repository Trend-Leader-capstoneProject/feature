"""Native boundary review: synthetic handles, buffers and SID only."""

import ctypes
import sys
import unittest
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import Mock, patch

import fr_b02b_windows_auth as auth


@unittest.skipUnless(sys.platform == "win32", "Windows ctypes ABI required")
class WindowsAuthNativeTests(unittest.TestCase):
    def exercise(self, failure=None):
        text = ctypes.create_unicode_buffer("S-1-5-21-100-200-300-1001")
        kernel = SimpleNamespace(
            GetCurrentProcess=Mock(return_value=-1),
            CloseHandle=Mock(return_value=failure != "close"),
            LocalFree=Mock(return_value=123 if failure == "free" else None),
        )

        def open_token(_process, _access, result):
            if failure == "open":
                return False
            ctypes.cast(result, ctypes.POINTER(wintypes.HANDLE))[0] = 123
            return True

        def information(_token, _kind, buffer, _size, needed):
            ctypes.cast(needed, ctypes.POINTER(wintypes.DWORD))[0] = 128
            if buffer is None:
                ctypes.set_last_error(5 if failure == "size" else 122)
                return False
            if failure == "query":
                return False
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0] = 456
            return True

        def convert(_sid, output):
            if failure == "convert":
                return False
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(text)
            return True

        security = SimpleNamespace(
            OpenProcessToken=Mock(side_effect=open_token),
            GetTokenInformation=Mock(side_effect=information),
            ConvertSidToStringSidW=Mock(side_effect=convert),
        )
        with patch.object(ctypes, "WinDLL", side_effect=[kernel, security]):
            if failure:
                with self.assertRaises(OSError):
                    auth.get_current_process_sid()
            else:
                self.assertEqual(auth.get_current_process_sid(), text.value)

        self.assertEqual(kernel.CloseHandle.call_count, 0 if failure == "open" else 1)
        owns_text = failure in (None, "free", "close")
        self.assertEqual(kernel.LocalFree.call_count, int(owns_text))
        if owns_text:
            self.assertEqual(kernel.LocalFree.call_args.args[0].value, ctypes.addressof(text))
        if failure != "open":
            self.assertEqual(kernel.CloseHandle.call_args.args[0].value, 123)
        self.assertEqual(kernel.GetCurrentProcess.restype, wintypes.HANDLE)
        self.assertEqual(kernel.LocalFree.restype, wintypes.HLOCAL)
        self.assertEqual(security.OpenProcessToken.argtypes[-1],
                         ctypes.POINTER(wintypes.HANDLE))
        self.assertEqual(security.ConvertSidToStringSidW.argtypes[-1],
                         ctypes.POINTER(wintypes.LPWSTR))

    def test_success_releases_allocated_text_and_token(self):
        self.exercise()

    def test_native_failures_release_only_owned_resources_and_block(self):
        for failure in ("open", "size", "query", "convert", "free", "close"):
            with self.subTest(failure=failure):
                self.exercise(failure)


if __name__ == "__main__":
    unittest.main()
