"""Explicit read-only Collector entry point, independent of FastAPI startup."""

import argparse
import json
import time
from datetime import datetime, timezone

from app.trend_collection.godot_release_collector import (
    CollectionError,
    build_candidate,
    collect,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview


def now_utc():
    return datetime.now(timezone.utc)


def run_cycles(runs, interval, *, fetch=collect, clock=now_utc,
               sleep=time.sleep, emit=print, project=build_candidate):
    """Sequential fixed-delay loop; runs=None means until stopped."""
    seen = set()
    index = 0
    failed = False
    while runs is None or index < runs:
        index += 1
        result = {
            "cycle": index, "status": "HOLD", "candidate": None,
            "publication_status": "NOT_FOR_PUBLICATION",
            "publish_authorization": "NONE", "database_write_performed": False,
        }
        try:
            candidate = project(fetch(), clock())
            identity = candidate["candidate_identity"]
            result.update(candidate_identity=identity)
            if identity in seen:
                result["status"] = "DUPLICATE_IN_PROCESS"
            else:
                seen.add(identity)
                result.update(status="NEW_PREVIEW_ONLY", candidate=candidate)
        except CollectionError as exc:
            failed = True
            result["reason"] = str(exc)
        result["observed_at_utc"] = clock().isoformat()
        emit(json.dumps(result, ensure_ascii=False))
        if runs is None or index < runs:
            sleep(interval)
    return 2 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    count = parser.add_mutually_exclusive_group()
    count.add_argument("--runs", type=int, default=1)
    count.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=21600)
    parser.add_argument("--rule-first", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.runs <= 100 or not 60 <= args.interval_seconds <= 86400:
        parser.error("runs: 1..100; interval: 60..86400 seconds")
    try:
        return run_cycles(None if args.continuous else args.runs,
                          args.interval_seconds,
                          emit=lambda line: print(line, flush=True),
                          project=(build_rule_first_preview if args.rule_first
                                   else build_candidate))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
