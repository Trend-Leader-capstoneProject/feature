"""One explicit exhibition category. Default execution prints an offline plan."""

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from typing import TextIO

import httpx2

from .d1_cli import _diagnostic, _readiness
from .d1_live_preview import CONFIRMATION_PHRASE
from .demo_search import (
    PROFILE_SCOPES,
    DemoSearchConfig,
    build_demo_plan,
    run_demo_preview,
)


def main(
    argv: list[str] | None = None, *, stdin: TextIO | None = None,
    stdout: TextIO | None = None, stderr: TextIO | None = None,
    execution_at: datetime | None = None,
    http_transport: httpx2.BaseTransport | None = None,
) -> int:
    """Preserve D1's TTY and exact confirmation rules; never echo unknown input."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    confirmation_accepted = False
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if args == ["--check-readiness"]:
            stdout.write(json.dumps({
                **_readiness(), "available_profiles": list(PROFILE_SCOPES),
            }) + "\n")
            return 0
        if not args:
            stdout.write(json.dumps({
                "status": "PROFILE_REQUIRED", "live_request_allowed": False,
                "available_profiles": list(PROFILE_SCOPES),
            }) + "\n")
            return 1
        if (
            len(args) < 2 or args[0] != "--profile"
            or args[1] not in PROFILE_SCOPES
            or args[2:] not in (
                [], ["--execute-live"], ["--execute-live", "--review-local"],
            )
        ):
            return _diagnostic(stderr, "BLOCKED_CONFIG", "INVALID_ARGUMENTS")
        if execution_at is not None and not isinstance(
            http_transport, httpx2.MockTransport,
        ):
            return _diagnostic(stderr, "BLOCKED_CONFIG", "INVALID_CONFIGURATION")
        plan = build_demo_plan(
            config=DemoSearchConfig(profile=args[1]), execution_at=execution_at,
        )
        if len(args) == 2:
            result = asdict(plan)
            result["start_date"] = plan.start_date.isoformat()
            result["end_date"] = plan.end_date.isoformat()
            stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
            return 0
        if not stdin.isatty() or not stdout.isatty():
            return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "INTERACTIVE_REQUIRED")
        stderr.write(
            f"Profile {plan.config.profile}, {plan.start_date}~{plan.end_date}. "
            f"Type {CONFIRMATION_PHRASE} to request one search:\n",
        )
        stderr.flush()
        confirmation = stdin.readline()
        if confirmation.endswith("\n"):
            confirmation = confirmation[:-1]
            if confirmation.endswith("\r"):
                confirmation = confirmation[:-1]
        if confirmation != CONFIRMATION_PHRASE:
            return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "CONFIRMATION_FAILED")
        confirmation_accepted = True
        preview = run_demo_preview(
            plan=plan, execute_live=True, interactive=True,
            confirmation=confirmation, api_key=os.environ.get("OPENAI_API_KEY"),
            http_transport=http_transport,
        )
        visible = dict(preview)
        material = visible.pop("review_only_candidates", [])
        visible["review_only_candidate_count"] = len(material)
        if "--review-local" in args:
            visible["review_only_candidates"] = material
        stdout.write(json.dumps(visible, ensure_ascii=False, allow_nan=False) + "\n")
        return 0 if preview["status"] in {
            "PREVIEW_READY", "PARTIAL_PREVIEW_READY", "EMPTY_RESULT",
            "NO_VALID_CANDIDATES",
        } else 1
    except (EOFError, KeyboardInterrupt):
        if confirmation_accepted:
            return _diagnostic(
                stderr, "UPSTREAM_ERROR", "EXECUTION_INTERRUPTED",
                search_execution="UNKNOWN",
            )
        return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "CANCELLED")
    except Exception:
        return _diagnostic(stderr, "UPSTREAM_ERROR", "UNEXPECTED_ERROR")


if __name__ == "__main__":
    raise SystemExit(main())
