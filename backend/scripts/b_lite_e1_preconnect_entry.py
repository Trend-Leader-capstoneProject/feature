"""B-Lite E1-W0: E0 + A-Lite pre-connect review, always fail closed.

This is not a Writer and has no database imports, sessions, or APPLY option.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.b_lite_e1_hold_boundary import inspect_manual_approval
from scripts.b_lite_exhibition_once import PreflightBlocked, check_file


def _blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "authorized_to_publish": False,
        "g6_approval": "HOLD",
        "database_connections": 0,
        "database_writes": 0,
    }


def inspect_preconnect(
    manifest_file: Path,
    approval_file: Path | None,
    comparison_sha256: str | None,
) -> dict[str, object]:
    """Run E0 then AL-02 without resolving any DB dependency.

    Neither an E0 REVIEW_ONLY result nor a matched approval file grants APPLY.
    Unexpected future changes to either result must also fail closed.
    """
    try:
        candidate = check_file(manifest_file)
    except PreflightBlocked as exc:
        return _blocked(str(exc))
    except OSError:
        return _blocked("INPUT_READ_FAILED")

    if (
        candidate.get("status") != "REVIEW_ONLY"
        or candidate.get("authorized_to_publish") is not False
        or candidate.get("g6_approval") != "HOLD"
        or candidate.get("database_connections") != 0
        or candidate.get("database_writes") != 0
    ):
        return _blocked("E0_UNEXPECTED_AUTHORIZATION")

    approval = inspect_manual_approval(approval_file, comparison_sha256)
    if (
        approval.get("status") != "BLOCKED"
        or approval.get("authorized_to_publish") is not False
        or approval.get("g6_approval") != "HOLD"
        or approval.get("database_connections") != 0
        or approval.get("database_writes") != 0
    ):
        return _blocked("E1_UNEXPECTED_AUTHORIZATION")

    return approval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B-Lite E1-W0 HOLD-only entry")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--comparison-sha256")
    args = parser.parse_args(argv)
    result = inspect_preconnect(
        args.input, args.approval_file, args.comparison_sha256
    )
    print(json.dumps(result, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
