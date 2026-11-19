"""Read-only, redacted environment evidence for the Phase 4B-2 DRAFT.

Run from PowerShell: python -B ./tools/fr_b02b_cli/diagnostics/phase4b2_environment_readonly.py
No directory/file creation, security setter, elevation, token duplication,
registration, external request or configuration fallback is performed.
Queries return diagnostics only, never an authorization/operational PASS.
"""

import ctypes as c
import json
from pathlib import Path
import stat
from ctypes import wintypes as w
from uuid import UUID

AUDIT_RESULT = {"probe": "native_readonly", "operational_approval": "NONE"}


def bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function


def main():
    AUDIT_RESULT["last_query"] = "native_bindings"
    kernel = c.WinDLL("kernel32", use_last_error=True)
    security = c.WinDLL("advapi32", use_last_error=True)
    shell = c.WinDLL("shell32", use_last_error=True)
    ole = c.WinDLL("ole32", use_last_error=True)
    ptr = c.c_void_p
    get_process = bind(kernel, "GetCurrentProcess", [], w.HANDLE)
    close = bind(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
    free = bind(kernel, "LocalFree", [ptr], ptr)
    task_free = bind(ole, "CoTaskMemFree", [ptr], None)
    known_folder = bind(shell, "SHGetKnownFolderPath",
                        [ptr, w.DWORD, w.HANDLE, c.POINTER(ptr)], c.c_long)
    open_token = bind(security, "OpenProcessToken",
                      [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL)
    token_info = bind(security, "GetTokenInformation",
                      [w.HANDLE, c.c_int, ptr, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
    equal_sid = bind(security, "EqualSid", [ptr, ptr], w.BOOL)
    named_sd = bind(security, "GetNamedSecurityInfoW", [w.LPWSTR, c.c_int, w.DWORD,
                    c.POINTER(ptr), ptr, c.POINTER(ptr), ptr, c.POINTER(ptr)], w.DWORD)
    sd_control = bind(security, "GetSecurityDescriptorControl",
                      [ptr, c.POINTER(w.WORD), c.POINTER(w.DWORD)], w.BOOL)

    def query(token, kind):
        fixed_size = {18: c.sizeof(w.DWORD), 20: c.sizeof(w.DWORD),
                      19: c.sizeof(w.HANDLE)}.get(kind)
        if fixed_size is not None:
            buffer = c.create_string_buffer(fixed_size)
            returned = w.DWORD()
            if not token_info(token, kind, buffer, len(buffer), c.byref(returned)):
                raise OSError(c.get_last_error(), "fixed token query failed")
            return buffer
        size = w.DWORD()
        returned = token_info(token, kind, None, 0, c.byref(size))
        error_code = c.get_last_error()
        if returned or error_code != 122:
            raise OSError(error_code, "token size query failed")
        if not 0 < size.value <= 65_536:
            raise OSError("unexpected token size")
        buffer = c.create_string_buffer(size.value)
        if not token_info(token, kind, buffer, len(buffer), c.byref(size)):
            raise OSError(c.get_last_error(), "token query failed")
        return buffer

    def token_summary(token):
        elevated = c.cast(query(token, 20), c.POINTER(w.DWORD))[0]
        elevation_type = c.cast(query(token, 18), c.POINTER(w.DWORD))[0]
        return {"is_elevated": bool(elevated), "elevation_type": {
            1: "Default", 2: "Full", 3: "Limited",
        }.get(elevation_type, "Unknown")}

    def security_summary(path):
        owner, dacl, descriptor = ptr(), ptr(), ptr()
        status = named_sd(str(path), 1, 0x5, c.byref(owner), None,
                          c.byref(dacl), None, c.byref(descriptor))
        if status:
            return {"sd_query": "UNVERIFIED", "win32_error_code": int(status)}
        try:
            control, revision = w.WORD(), w.DWORD()
            if not sd_control(descriptor, c.byref(control), c.byref(revision)):
                raise OSError("security descriptor control query failed")
            # No SDDL, account names, SID strings or ACE contents are emitted.
            count = c.cast(dacl, c.POINTER(w.WORD))[2] if dacl.value else None
            return {"sd_query": "SUCCESS", "owner_present": bool(owner.value),
                    "dacl_present": bool(control.value & 0x4),
                    "dacl_non_null": bool(dacl.value), "ace_count": count,
                    "dacl_protected": bool(control.value & 0x1000)}
        finally:
            if descriptor.value and free(descriptor):
                raise OSError("security descriptor release failed")

    def probe_path(label, path):
        # Walk ancestors without following a pre-existing reparse component.
        for component in (*reversed(path.parents), path):
            try:
                info = component.lstat()
            except FileNotFoundError:
                return {"label": label, "existence": "ABSENT_OR_PARENT_ABSENT"}
            except OSError as error:
                return {"label": label, "existence": "UNVERIFIED",
                        "error_type": type(error).__name__}
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                return {"label": label, "existence": "REPARSE_COMPONENT_NO_DESCENT"}
        try:
            summary = security_summary(path)
        except OSError as error:
            summary = {"sd_query": "UNVERIFIED", "error_type": type(error).__name__}
        return {"label": label, "existence": "EXISTS", **summary}

    result = AUDIT_RESULT
    result["last_query"] = "known_folder"
    guid = c.create_string_buffer(UUID("62ab5d82-fdc1-4dc3-a9dd-070d1d495d97").bytes_le, 16)
    location = ptr()
    # Flags=0: KF_FLAG_CREATE is never requested.
    folder_status = known_folder(guid, 0, None, c.byref(location))
    targets = []
    if folder_status != 0:
        result["program_data"] = {"query": "UNVERIFIED",
                                  "hresult": hex(folder_status & 0xFFFFFFFF)}
    else:
        try:
            program_data = Path(c.wstring_at(location))
        finally:
            task_free(location)
        result["program_data"] = {
            "query": "SUCCESS", "on_C": program_data.drive.casefold() == "c:",
            "location": program_data.as_posix() if program_data == Path("C:/ProgramData")
                        else "NONSTANDARD_LOCATION_REDACTED",
        }
        proposed = program_data / "TrendLeader" / "ProtectedReview"
        targets = [
            ("program_data_base", program_data),
            ("proposed_app_parent", program_data / "TrendLeader"),
            ("proposed_primary_root", proposed),
            ("proposed_config", proposed / "Config"),
            ("proposed_settings_file", proposed / "Config" / "settings.json"),
            ("proposed_allowlist_file", proposed / "Config" / "reviewers.json"),
            ("proposed_store", proposed / "Store"),
        ]
    targets.extend([
        ("E_base", Path("E:/")),
        ("proposed_backup_root", Path("E:/TrendLeaderProtectedReview")),
    ])
    result["paths"] = []
    for label, path in targets:
        result["last_query"] = label
        result["paths"].append(probe_path(label, path))

    result["last_query"] = "primary_token"
    token = w.HANDLE()
    if not open_token(get_process(), 0x8, c.byref(token)):  # TOKEN_QUERY only.
        result["token"] = {"query": "UNVERIFIED"}
    else:
        try:
            result["token"] = {"query": "SUCCESS", **token_summary(token)}
            result["last_query"] = "linked_token"
            try:
                linked_data = query(token, 19)
                linked = w.HANDLE(c.cast(linked_data, c.POINTER(w.HANDLE))[0])
            except OSError:
                result["linked_token"] = {"query": "UNAVAILABLE_NO_ELEVATION_ATTEMPT"}
            else:
                try:
                    primary_user, linked_user = query(token, 1), query(linked, 1)
                    same_user = equal_sid(c.cast(primary_user, c.POINTER(ptr))[0],
                                          c.cast(linked_user, c.POINTER(ptr))[0])
                    result["linked_token"] = {"query": "SUCCESS", "same_user": bool(same_user),
                                               **token_summary(linked)}
                finally:
                    if not close(linked):
                        raise OSError("linked query handle release failed")
        finally:
            if not close(token):
                raise OSError("query handle release failed")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Audit failure is explicit, but diagnostics never contain private data.
        print(json.dumps({**AUDIT_RESULT, "query": "FAILED",
                          "error_type": type(error).__name__,
                          "error_code": getattr(error, "errno", None)}))
        raise SystemExit(1) from None
