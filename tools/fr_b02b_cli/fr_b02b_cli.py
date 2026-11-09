"""FR-B02b independent CLI: simulations and Phase 4A local attestations.

Only observe-a1-zip opens a browser for a human; the CLI never fetches content.
No operational evidence, DB access, or Gate changes. No output grants publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
import webbrowser
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import fr_b02b_observation as observation
from fr_b02b_a1_adapter import (
    A1InspectionError,
    inspect_a1_paths,
    inspect_a1_zip,
    load_a1_snapshot,
)

INPUT_SCHEMA = "FR_B02B_SIM_INPUT_V01"
RECORD_SCHEMA = "FR_B02B_SIMULATION_V01"
INDEX_SCHEMA = "FR_B02B_SIM_INDEX_V01"
INPUT_KEYS = frozenset({
    "schema", "trend_ref", "content_ref", "review_evidence_id", "source_url",
    "source_title", "claim_note",
})
RECORD_KEYS = frozenset({
    "schema", "simulation_only", "evidence_id", "trend_ref", "content_ref",
    "review_evidence_id", "source_url", "source_title", "claim_note",
    "event_kind", "observation_result", "review_result",
    "confirmation_clicked_at", "recorded_at", "observer_ref", "g6_status",
    "authorized_to_publish",
})
INDEX_KEYS = frozenset({
    "schema", "evidence_id", "artifact_file", "artifact_sha256", "trend_ref",
    "content_ref", "source_url", "status",
})
MAX_INPUT_BYTES = 16_384
MAX_EVIDENCE_BYTES = 16_384
SHA256_REF_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")


class SimulationError(ValueError):
    """Invalid synthetic fixture or PoC record; never recover by guessing."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SimulationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SimulationError("invalid UTF-8 JSON input") from exc
    if not isinstance(value, dict):
        raise SimulationError("JSON root must be an object")
    return value


def _read_limited(path: Path, limit: int = MAX_INPUT_BYTES) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise SimulationError("expected an ordinary input file")
    if path.stat().st_size > limit:
        raise SimulationError("file size limit exceeded")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise SimulationError("file size limit exceeded")
    return raw


def _string(value: Any, name: str, max_length: int = 255) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > max_length:
        raise SimulationError(f"invalid field: {name}")
    if any(ord(char) < 32 for char in value):
        raise SimulationError(f"control character in field: {name}")
    return value


def load_fixture_bytes(raw: bytes) -> dict[str, str]:
    if len(raw) > MAX_INPUT_BYTES:
        raise SimulationError("file size limit exceeded")
    obj = _parse_json(raw)
    if set(obj) != INPUT_KEYS or obj.get("schema") != INPUT_SCHEMA:
        raise SimulationError("unsupported simulation input schema or fields")
    for name in INPUT_KEYS - {"schema"}:
        _string(obj[name], name, max_length=512 if name == "source_url" else 255)
    for field in ("trend_ref", "review_evidence_id"):
        if not obj[field].startswith("SIM-"):
            raise SimulationError(f"real identifier rejected: {field}")
    if not SHA256_REF_PATTERN.fullmatch(obj["content_ref"]):
        raise SimulationError("invalid synthetic content_ref")
    url = urlsplit(obj["source_url"])
    if (
        url.scheme != "https"
        or url.netloc != "example.test"
        or not url.path.startswith("/")
        or url.username is not None
        or url.password is not None
        or url.fragment
    ):
        raise SimulationError("only synthetic https://example.test paths are accepted")
    return obj


def canonical_bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8") + b"\n"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def utc_iso(now: Callable[[], datetime]) -> str:
    value = now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise SimulationError("timezone-aware clock required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_simulation_record(
    fixture: dict[str, str], now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
) -> dict[str, Any]:
    confirmation = utc_iso(now)
    return {
        "schema": RECORD_SCHEMA,
        "simulation_only": True,
        "evidence_id": "SIM-OBS-" + uuid.uuid4().hex,
        "trend_ref": fixture["trend_ref"],
        "content_ref": fixture["content_ref"],
        "review_evidence_id": fixture["review_evidence_id"],
        "source_url": fixture["source_url"],
        "source_title": fixture["source_title"],
        "claim_note": fixture["claim_note"],
        "event_kind": "SIMULATION",
        "observation_result": "SIMULATED_ONLY",
        "review_result": "HOLD",
        "confirmation_clicked_at": confirmation,
        "recorded_at": utc_iso(now),
        "observer_ref": "SIM-OBSERVER-NOT_AUTHENTICATED",
        "g6_status": "HOLD",
        "authorized_to_publish": False,
    }


def build_index(record: dict[str, Any], record_bytes: bytes) -> dict[str, str]:
    return {
        "schema": INDEX_SCHEMA,
        "evidence_id": record["evidence_id"],
        "artifact_file": "observation.json",
        "artifact_sha256": sha256(record_bytes),
        "trend_ref": record["trend_ref"],
        "content_ref": record["content_ref"],
        "source_url": record["source_url"],
        "status": "SIMULATION_ONLY_HOLD",
    }


def _write_fsynced(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def store_simulation(record: dict[str, Any], root: Path) -> Path:
    """Stage two PoC files then move together; not a verified durable journal."""
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SimulationError("output directory is invalid")
    root.mkdir(parents=True, exist_ok=True)
    path = root / record["evidence_id"]
    if path.exists():
        raise SimulationError("simulation event already exists")
    staging: Path | None = Path(tempfile.mkdtemp(prefix=".sim-staging-", dir=root))
    try:
        record_bytes = canonical_bytes(record)
        index_bytes = canonical_bytes(build_index(record, record_bytes))
        _write_fsynced(staging / "observation.json", record_bytes)
        _write_fsynced(staging / "index.json", index_bytes)
        # No existing record may be deliberately replaced; not concurrency-safe for production.
        if path.exists():
            raise SimulationError("simulation event already exists")
        staging.rename(path)
        staging = None
        return path
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def verify_simulation(record_dir: Path, fixture: dict[str, str]) -> dict[str, str]:
    """Detect missing/tampered files and binding mismatch; cannot authenticate an actor."""
    if not record_dir.is_dir() or record_dir.is_symlink():
        raise SimulationError("simulation record directory missing or invalid")
    record_bytes = _read_limited(record_dir / "observation.json", MAX_EVIDENCE_BYTES)
    index_bytes = _read_limited(record_dir / "index.json", MAX_EVIDENCE_BYTES)
    record = _parse_json(record_bytes)
    index = _parse_json(index_bytes)
    if set(record) != RECORD_KEYS or set(index) != INDEX_KEYS:
        raise SimulationError("unsupported simulation record fields")
    if record.get("schema") != RECORD_SCHEMA or index.get("schema") != INDEX_SCHEMA:
        raise SimulationError("unsupported simulation record schema")
    if canonical_bytes(record) != record_bytes or canonical_bytes(index) != index_bytes:
        raise SimulationError("noncanonical simulation record")
    if index.get("artifact_sha256") != sha256(record_bytes):
        raise SimulationError("simulation record digest mismatch")
    if (
        index.get("artifact_file") != "observation.json"
        or index.get("evidence_id") != record.get("evidence_id")
        or record.get("evidence_id") != record_dir.name
        or not isinstance(record.get("evidence_id"), str)
        or not record["evidence_id"].startswith("SIM-OBS-")
    ):
        raise SimulationError("simulation record index mismatch")
    for name in ("trend_ref", "content_ref", "source_url"):
        if index.get(name) != record.get(name):
            raise SimulationError(f"index binding mismatch: {name}")
    for name in INPUT_KEYS - {"schema"}:
        if record.get(name) != fixture[name]:
            raise SimulationError(f"fixture binding mismatch: {name}")
    if not (
        record.get("simulation_only") is True
        and record.get("event_kind") == "SIMULATION"
        and record.get("observation_result") == "SIMULATED_ONLY"
        and record.get("review_result") == "HOLD"
        and record.get("g6_status") == "HOLD"
        and record.get("authorized_to_publish") is False
        and record.get("observer_ref") == "SIM-OBSERVER-NOT_AUTHENTICATED"
        and index.get("status") == "SIMULATION_ONLY_HOLD"
    ):
        raise SimulationError("unsafe simulation status")
    for name in ("confirmation_clicked_at", "recorded_at"):
        try:
            value = datetime.fromisoformat(record[name].replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError) as exc:
            raise SimulationError(f"invalid simulation timestamp: {name}") from exc
        if value.utcoffset() is None:
            raise SimulationError(f"naive timestamp: {name}")
    return {
        "evidence_id": record["evidence_id"],
        "status": "PASS_SIMULATION_ONLY",
        "publish_authorization": "NONE",
    }


def run_cli(argv: list[str] | None = None, *, input_func: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(description="FR-B02b local CLI; G5/G6 HOLD, no publication")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="display synthetic candidate, without writing")
    inspect_cmd.add_argument("--fixture", type=Path, required=True)
    simulate_cmd = sub.add_parser("simulate", help="one explicit synthetic confirmation; NO real evidence")
    simulate_cmd.add_argument("--fixture", type=Path, required=True)
    simulate_cmd.add_argument("--output-dir", type=Path, required=True)
    verify_cmd = sub.add_parser("verify", help="verify synthetic record and unchanged input binding")
    verify_cmd.add_argument("--fixture", type=Path, required=True)
    verify_cmd.add_argument("--record-dir", type=Path, required=True)
    a1_cmd = sub.add_parser(
        "inspect-a1", help="read-only A1 v0.2 original-schema single-item inspection; never approval"
    )
    a1_cmd.add_argument("--approvals", type=Path, required=True)
    a1_cmd.add_argument("--batch", type=Path, required=True)
    a1_zip_cmd = sub.add_parser(
        "inspect-a1-zip", help="read A1 originals directly from the known G5 P1 ZIP; no extraction"
    )
    a1_zip_cmd.add_argument("--zip", type=Path, required=True)
    observe_cmd = sub.add_parser("observe-a1-zip", help="record one local human attestation; review HOLD")
    observe_cmd.add_argument("--zip", type=Path, required=True)
    observe_cmd.add_argument("--output-dir", type=Path, required=True)
    verify_observation_cmd = sub.add_parser("verify-observation", help="read-only local integrity verification")
    verify_observation_cmd.add_argument("--zip", type=Path, required=True)
    verify_observation_cmd.add_argument("--record-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command in ("observe-a1-zip", "verify-observation"):
        try:
            if args.command == "verify-observation":
                result = observation.verify_observation(args.zip, args.record_dir)
            else:
                snapshot = load_a1_snapshot(args.zip)
                observation.require_observation_candidate(snapshot)
                observation.validate_output_dir(args.output_dir, args.zip)
                print(f"Title: {snapshot.title}")
                print(f"Summary: {snapshot.summary}")
                print(f"Editorial source label: {snapshot.source_title}")
                print(f"Approved HTTPS URL: {snapshot.source_url}")
                print("브라우저 실행은 실제 열람·권리·신원 인증이 아닙니다. G5/G6 HOLD.")
                if not webbrowser.open(snapshot.source_url):
                    raise observation.ObservationError("browser launch failed")
                answer = input_func(
                    "원문·페이지 대상·URL·내용이 승인 스냅샷과 일치하고, 지금 직접 확인해 "
                    "새 출처 근거로 채택할 때만 정확히 YES를 입력하세요. "
                    "단순 링크 재확인·내용 변경·의심스러운 리디렉션은 취소하세요: "
                )
                if answer != "YES":
                    print("CANCELLED")
                    return 2
                confirmed_at = observation.capture_confirmation_time()
                result = observation.record_observation(
                    snapshot, args.zip, args.output_dir, confirmed_at
                )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            print("LOCAL INTEGRITY/ATTESTATION ONLY; 운영 P4 Evidence·게시 승인 아님.")
            return 0
        except (EOFError, KeyboardInterrupt):
            print("CANCELLED")
            return 2
        except (observation.ObservationError, A1InspectionError) as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 1
        except (OSError, ValueError, RuntimeError, webbrowser.Error) as exc:
            # Do not leak full user paths or untrusted input through OS errors.
            print(f"BLOCKED: local input/browser/storage failure ({type(exc).__name__})", file=sys.stderr)
            return 1

    try:
        if args.command == "inspect-a1-zip":
            result = inspect_a1_zip(args.zip)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "inspect-a1":
            result = inspect_a1_paths(args.approvals, args.batch)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        raw = _read_limited(args.fixture)
        fixture = load_fixture_bytes(raw)
        if args.command == "inspect":
            print("SYNTHETIC ONLY / NO LIVE SOURCE VERIFIED / G5-G6 HOLD")
            print(f"Title: {fixture['source_title']}")
            print(f"URL: {fixture['source_url']}")
            print(f"Claim note: {fixture['claim_note']}")
            return 0
        if args.command == "simulate":
            print("SYNTHETIC-ONLY SIMULATION. No browser request or real observation occurs.")
            print(f"URL: {fixture['source_url']}")
            answer = input_func("Simulate ONE confirmation? Type YES, otherwise cancel: ")
            if answer != "YES":
                print("CANCELLED: no record created")
                return 2
            # Detect fixture changes between preview and write; original byte identity matters.
            if _read_limited(args.fixture) != raw:
                raise SimulationError("fixture changed during confirmation")
            record = build_simulation_record(fixture)
            folder = store_simulation(record, args.output_dir)
            print(f"SIMULATION_RECORDED: {folder}")
            print("NOT PRODUCTION EVIDENCE. NOT ACCEPTED. G5/G6 HOLD.")
            return 0
        if args.command == "verify":
            result = verify_simulation(args.record_dir, fixture)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
    except (SimulationError, A1InspectionError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
