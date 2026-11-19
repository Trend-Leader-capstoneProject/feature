"""Private reviewer authorization boundary; no operational source configured."""

import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fr_b02b_observation import _safe_local_path

SCHEMA = "FR_B02B_REVIEWER_ALLOWLIST_V1"
MAX_ALLOWLIST_BYTES = 65_536
SID_PATTERN = re.compile(r"S-1-(?:[0-9]+|0x[0-9a-fA-F]+)(?:-[0-9]+){0,15}\Z")


class AllowlistError(ValueError):
    """Safe category-only authorization failure."""


class AllowlistNotConfigured(AllowlistError):
    """No verified, pre-managed operational source exists yet."""


@dataclass(frozen=True)
class AllowlistSource:
    """Internal source; synthetic tests supply path/protection verification.

    A future operational provider must validate the file AND its ancestor access
    boundary. Neither existence nor a digest alone proves protection.
    """

    path: Path
    verify_protection: Callable[[Path], bool]


def managed_allowlist_source() -> AllowlistSource:
    """No guessed path, environment fallback or unverified default verifier."""
    raise AllowlistNotConfigured("reviewer allowlist is not configured")


def _require_protection(source: AllowlistSource, path: Path) -> None:
    try:
        verified = source.verify_protection(path)
    except (OSError, ValueError):
        # Operational verification failures cannot authorize. Programming errors
        # must remain visible rather than masquerading as bad permissions.
        raise AllowlistError("reviewer allowlist protection failure") from None
    if verified is not True:
        raise AllowlistError("reviewer allowlist protection failure")


def _signature(info: os.stat_result) -> tuple[int, ...]:
    # Windows path/handle st_ctime can report different values (and st_ctime is
    # deprecated there). Identity, size and mtime plus both protection checks
    # are used; this is not a substitute for the future native protected reader.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns)


def _read_protected_bytes(source: AllowlistSource) -> bytes:
    try:
        if not isinstance(source.path, Path) or not source.path.is_absolute():
            raise ValueError("absolute managed path required")
        path = _safe_local_path(source.path)
    except (OSError, ValueError):
        raise AllowlistError("reviewer allowlist protection failure") from None
    _require_protection(source, path)
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not before.st_ino:
            raise AllowlistError("reviewer allowlist protection failure")
        if before.st_size > MAX_ALLOWLIST_BYTES:
            raise AllowlistError("invalid reviewer allowlist")
        with path.open("rb") as file:
            if _signature(os.fstat(file.fileno())) != _signature(before):
                raise AllowlistError("reviewer allowlist changed during validation")
            raw = file.read(MAX_ALLOWLIST_BYTES + 1)
            _require_protection(source, path)
            # Compare the opened file and named file after the second protection
            # check. Read data is never replaced with unvalidated later bytes.
            if (_signature(os.fstat(file.fileno())) != _signature(before)
                    or _signature(path.lstat()) != _signature(before)
                    or len(raw) != before.st_size):
                raise AllowlistError("reviewer allowlist changed during validation")
    except AllowlistError:
        raise
    except (OSError, ValueError):
        raise AllowlistError("reviewer allowlist unavailable") from None
    if len(raw) > MAX_ALLOWLIST_BYTES:
        raise AllowlistError("invalid reviewer allowlist")
    return raw


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _invalid_constant(_value):
    raise ValueError("nonfinite JSON value")


def _valid_sid(value) -> bool:
    if not isinstance(value, str) or len(value) > 184 or not SID_PATTERN.fullmatch(value):
        return False
    parts = value.split("-")
    authority = int(parts[2], 16 if parts[2].startswith("0x") else 10)
    return authority < 2**48 and all(int(part) < 2**32 for part in parts[3:])


def _parse_reviewers(raw: bytes) -> dict[str, bool]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_invalid_constant)
        if (not isinstance(value, dict) or set(value) != {"schema", "reviewers"}
                or value["schema"] != SCHEMA or not isinstance(value["reviewers"], list)):
            raise ValueError("invalid allowlist fields")
        reviewers = {}
        for entry in value["reviewers"]:
            if (not isinstance(entry, dict) or set(entry) != {"sid", "active", "role"}
                    or not _valid_sid(entry["sid"]) or type(entry["active"]) is not bool
                    or entry["role"] != "EVIDENCE_REVIEWER" or entry["sid"] in reviewers):
                raise ValueError("invalid reviewer entry")
            reviewers[entry["sid"]] = entry["active"]
        return reviewers
    except (UnicodeError, ValueError, RecursionError):
        raise AllowlistError("invalid reviewer allowlist") from None


def require_authorized_sid(sid: str, source: AllowlistSource | None = None) -> str:
    """Check one exact active SID/role using a protected byte snapshot.

    Supplying a source is an internal dependency for synthetic tests only until
    operational provisioning and an actual Windows protection verifier exist.
    """
    if source is None:
        try:
            source = managed_allowlist_source()
        except AllowlistNotConfigured:
            raise
        except (OSError, ValueError):
            # Retrieving managed configuration is also a trust boundary.
            raise AllowlistError("reviewer allowlist unavailable") from None
    if not isinstance(source, AllowlistSource):
        raise AllowlistError("reviewer allowlist protection failure")
    reviewers = _parse_reviewers(_read_protected_bytes(source))
    if not isinstance(sid, str) or reviewers.get(sid) is not True:
        raise AllowlistError("reviewer is not authorized")
    return sid
