"""D1 내부 CLI. 기본은 오프라인 계획이며 import 시 실행하지 않는다.

TTY/확인 문구는 사용자 인증이 아닌 실수 방지 절차다. 유료 실행에 대한
별도 운영 승인을 대체하지 않는다. API Key·예외·원본 응답을 진단하지 않는다.
"""

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from typing import TextIO

import httpx2

from .d1_live_preview import CONFIRMATION_PHRASE, run_live_preview
from .gate_d_preflight import build_preflight_plan


def _diagnostic(stream: TextIO, status: str, reason: str) -> int:
    stream.write(json.dumps({"status": status, "reason_codes": [reason]}) + "\n")
    return 1


def main(
    argv: list[str] | None = None, *, stdin: TextIO | None = None,
    stdout: TextIO | None = None, stderr: TextIO | None = None,
    execution_at: datetime | None = None,
    http_transport: httpx2.BaseTransport | None = None,
) -> int:
    """확인 후에만 키를 읽고 D1 Service를 호출한다. 전송/시각 주입은 내부용."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        # Fixed grammar avoids argparse echoing arbitrary arguments (e.g. keys).
        if args not in ([], ["--execute-live"]):
            return _diagnostic(stderr, "BLOCKED_CONFIG", "INVALID_ARGUMENTS")
        # Explicit synthetic dates cannot affect a real execution's calendar.
        if execution_at is not None and not isinstance(
            http_transport, httpx2.MockTransport,
        ):
            return _diagnostic(stderr, "BLOCKED_CONFIG", "INVALID_CONFIGURATION")
        plan = build_preflight_plan(execution_at=execution_at)
        if not args:
            result = asdict(plan)
            result["start_date"] = plan.start_date.isoformat()
            result["end_date"] = plan.end_date.isoformat()
            stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
            return 0
        if not stdin.isatty() or not stdout.isatty():
            return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "INTERACTIVE_REQUIRED")
        stderr.write(f"Type {CONFIRMATION_PHRASE} to request one search:\n")
        stderr.flush()
        confirmation = stdin.readline()
        # Strip only the terminal line ending; spaces are not confirmation.
        if confirmation.endswith("\n"):
            confirmation = confirmation[:-1]
            if confirmation.endswith("\r"):
                confirmation = confirmation[:-1]
        if confirmation != CONFIRMATION_PHRASE:
            return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "CONFIRMATION_FAILED")
        preview = run_live_preview(
            plan=plan, execute_live=True, interactive=True,
            confirmation=confirmation, api_key=os.environ.get("OPENAI_API_KEY"),
            http_transport=http_transport,
        )
        stdout.write(json.dumps(preview, ensure_ascii=False, allow_nan=False) + "\n")
        return 0 if preview["status"] in {
            "PREVIEW_READY", "EMPTY_RESULT", "NO_VALID_CANDIDATES",
        } else 1
    except (EOFError, KeyboardInterrupt):
        return _diagnostic(stderr, "LIVE_NOT_AUTHORIZED", "CANCELLED")
    except Exception:
        return _diagnostic(stderr, "UPSTREAM_ERROR", "UNEXPECTED_ERROR")


if __name__ == "__main__":
    raise SystemExit(main())
