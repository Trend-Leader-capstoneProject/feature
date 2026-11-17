"""B-Lite E1 A-Lite HOLD-only gate: no DB connector and no APPLY path.

This is a negative-path prototype. Matching a manual document hash does not
establish the authority, authenticity, or current validity of a G6 approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

MAX_APPROVAL_BYTES = 1_000_000
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


def _blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "authorized_to_publish": False,
        "g6_approval": "HOLD",
        "database_connections": 0,
        "database_writes": 0,
    }


def inspect_manual_approval(
    approval_file: Path | None,
    comparison_sha256: str | None,
) -> dict[str, object]:
    """Check only file presence and byte digest; always refuse publication.

    comparison_sha256 is an untrusted *comparison value*, not an independently
    authenticated approval source. No file content can authorize APPLY here.
    """
    if approval_file is None:
        return _blocked("APPROVAL_DOCUMENT_MISSING")
    if comparison_sha256 is None:
        return _blocked("COMPARISON_HASH_MISSING")
    if SHA256_PATTERN.fullmatch(comparison_sha256) is None:
        return _blocked("INVALID_COMPARISON_HASH")

    try:
        if approval_file.is_symlink():
            return _blocked("APPROVAL_PATH_NOT_ALLOWED")
        if not approval_file.is_file():
            return _blocked("APPROVAL_DOCUMENT_MISSING")
        if approval_file.stat().st_size > MAX_APPROVAL_BYTES:
            return _blocked("APPROVAL_DOCUMENT_TOO_LARGE")
        contents = approval_file.read_bytes()
    except OSError:
        return _blocked("APPROVAL_DOCUMENT_READ_FAILED")

    if len(contents) > MAX_APPROVAL_BYTES:
        return _blocked("APPROVAL_DOCUMENT_TOO_LARGE")
    digest = hashlib.sha256(contents).hexdigest()
    if digest != comparison_sha256.lower():
        return _blocked("APPROVAL_DOCUMENT_HASH_MISMATCH")

    # IMPORTANT: HOLD is unconditional even if the document contains 'PASS'.
    # No independent G6 identity/authority, scope, revocation, or Gate evidence
    # verifier exists. Never infer it from the matched hash or text.
    return _blocked("G6_INDEPENDENT_AUTH_NOT_VERIFIED")


def test_only_writer_entry_probe(
    approval_file: Path | None,
    comparison_sha256: str | None,
    *,
    connector: Callable[[], object],
) -> dict[str, object]:
    """Test seam to assert rejected requests never invoke the connector.

    Not an operational Writer. The callable is intentionally never invoked.
    """
    del connector
    return inspect_manual_approval(approval_file, comparison_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E1 A-Lite HOLD-only inspection")
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--comparison-sha256")
    args = parser.parse_args(argv)
    result = inspect_manual_approval(args.approval_file, args.comparison_sha256)
    print(json.dumps(result, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
