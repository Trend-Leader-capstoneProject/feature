"""Read the current process TokenUser SID; no username or manual-ID fallback.

Native contracts:
https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken
https://learn.microsoft.com/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation
https://learn.microsoft.com/windows/win32/api/sddl/nf-sddl-convertsidtostringsidw
"""

import sys


def get_current_process_sid() -> str:
    """Query only the primary process token, releasing its native resources.

    Returning an SID does not check reviewer authorization or protected ACLs.
    Windows/API failures raise OSError; the Service owns the BLOCKED policy.
    """
    if sys.platform != "win32":
        raise OSError("Windows process token unavailable")

    import ctypes
    from ctypes import wintypes

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    class TokenUser(ctypes.Structure):
        _fields_ = [("User", SidAndAttributes)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    security.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
    ]
    security.OpenProcessToken.restype = wintypes.BOOL
    security.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    security.GetTokenInformation.restype = wintypes.BOOL
    security.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR),
    ]
    security.ConvertSidToStringSidW.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    token_query, token_user, insufficient_buffer = 0x0008, 1, 122
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), token_query,
                                     ctypes.byref(token)):
        raise OSError("process token query failed")
    try:
        needed = wintypes.DWORD()
        if security.GetTokenInformation(token, token_user, None, 0, ctypes.byref(needed)):
            raise OSError("unexpected token information response")
        if ctypes.get_last_error() != insufficient_buffer:
            raise OSError("token information size unavailable")
        if not ctypes.sizeof(TokenUser) <= needed.value <= 65_536:
            raise OSError("invalid token information size")
        buffer = ctypes.create_string_buffer(needed.value)
        if not security.GetTokenInformation(token, token_user, buffer, len(buffer),
                                             ctypes.byref(needed)):
            raise OSError("token user query failed")
        sid = ctypes.cast(buffer, ctypes.POINTER(TokenUser)).contents.User.Sid
        text = wintypes.LPWSTR()
        if not security.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise OSError("process SID conversion failed")
        try:
            if not text.value:
                raise OSError("empty process SID")
            return text.value
        finally:
            if kernel.LocalFree(ctypes.cast(text, wintypes.HLOCAL)):
                raise OSError("process SID buffer release failed")
    finally:
        if not kernel.CloseHandle(token):
            raise OSError("process token release failed")
