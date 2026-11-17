"""B-Lite exhibition input preflight; intentionally has no publish or DB path."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "B_LITE_EXHIBITION_REVIEW_V1"
PROFILE = "MVP_A_EXHIBITION_20261118_19"
PARENTS = frozenset(
    {"FASHION", "BEAUTY", "GAME", "FOOD", "ENTERTAINMENT", "IT_DIGITAL"}
)
DEMO_NOTICE = "가상의 시연 데이터입니다. 실제 검색·수집 결과가 아닙니다."
MAX_BYTES = 1_000_000
MAX_RECORDS = 36


class PreflightBlocked(ValueError):
    """An input cannot proceed even to manual review."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PreflightBlocked(reason)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PreflightBlocked("NON_FINITE_JSON_NUMBER")


def _text(value: object, *, max_length: int = 255) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= max_length
        and value == value.strip()
        and not any(ord(ch) < 32 for ch in value)
    )


def _external_https(value: object) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        return (
            parsed.scheme == "https"
            and bool(host)
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and host not in {"localhost", "example.com", "example.org", "example.net"}
            and not host.endswith((".localhost", ".test", ".invalid"))
            and host not in {"google.com", "www.google.com", "trends.google.com"}
        )
    except ValueError:
        return False


def _validate_record(record: object) -> tuple[str, str]:
    _require(isinstance(record, dict), "INVALID_RECORD")
    kind = record.get("kind")
    allowed = ({"kind", "title", "summary", "thumbnail_url",
                "google_rss_derived", "parent_code", "child_name",
                "source_url", "source_title"})
    if kind == "REVIEWED_REAL":
        allowed |= {"review_evidence_id", "content_ref", "source_review",
                    "source_title_origin", "source_label_evidence_id"}
    _require(set(record) <= allowed, "UNRECOGNIZED_RECORD_FIELD")
    _require(kind in ("REVIEWED_REAL", "SYNTHETIC_DEMO"), "INVALID_KIND")
    title = record.get("title")
    _require(_text(title), "INVALID_TITLE")
    _require(record.get("thumbnail_url", "UNSET") is None, "THUMBNAIL_NOT_ALLOWED")
    _require(record.get("google_rss_derived") is False, "GOOGLE_RSS_NOT_EXCLUDED")
    root = record.get("parent_code")
    _require(isinstance(root, str) and root in PARENTS, "INVALID_ROOT_CATEGORY")
    _require(_text(record.get("child_name"), max_length=100), "INVALID_CHILD_CATEGORY")

    if kind == "SYNTHETIC_DEMO":
        _require(title.startswith("【DEMO】 "), "DEMO_LABEL_MISSING")
        summary = record.get("summary")
        _require(
            isinstance(summary, str) and DEMO_NOTICE in summary,
            "DEMO_DISCLOSURE_MISSING",
        )
        _require(record.get("source_url", "UNSET") is None, "DEMO_FAKE_SOURCE")
        _require(record.get("source_title", "UNSET") is None, "DEMO_FAKE_SOURCE")
        _require(record.get("review_evidence_id") is None, "DEMO_G4_IMPERSONATION")
        _require(record.get("content_ref") is None, "DEMO_G4_IMPERSONATION")
        return (kind, title.casefold())

    _require(not title.startswith("【DEMO】"), "REAL_MISLABELED")
    _require(_external_https(record.get("source_url")), "INVALID_SOURCE_URL")
    _require(
        _text(record.get("review_evidence_id"), max_length=120),
        "G4_EVIDENCE_MISSING",
    )
    content_ref = record.get("content_ref")
    _require(
        isinstance(content_ref, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", content_ref) is not None,
        "CONTENT_REF_MISSING",
    )
    _require(
        record.get("source_review") == "URL_TITLE_KEY_CLAIMS_VERIFIED",
        "SOURCE_REVIEW_MISSING",
    )
    origin = record.get("source_title_origin")
    label = record.get("source_title")
    if origin == "NONE":
        _require(label is None and record.get("source_label_evidence_id") is None,
                 "INVALID_SOURCE_LABEL")
    elif origin == "EDITORIAL_LABEL":
        _require(
            _text(label, max_length=80)
            and "<" not in label and ">" not in label
            and _text(record.get("source_label_evidence_id"), max_length=120),
            "INVALID_SOURCE_LABEL",
        )
    else:
        raise PreflightBlocked("INVALID_SOURCE_LABEL_ORIGIN")
    summary = record.get("summary")
    _require(summary is None or _text(summary, max_length=2000), "INVALID_SUMMARY")
    return (kind, title.casefold())


def inspect_manifest(data: object) -> dict[str, object]:
    """Validate declarations without certifying approval or publication."""
    _require(isinstance(data, dict), "INVALID_MANIFEST")
    _require(set(data) <= {"schema", "profile_id", "approval_scope",
                            "g6_status", "batch_id", "records"},
             "UNRECOGNIZED_MANIFEST_FIELD")
    _require(data.get("schema") == SCHEMA, "SCHEMA_MISMATCH")
    _require(data.get("profile_id") == PROFILE, "PROFILE_MISMATCH")
    _require(data.get("approval_scope") == "REVIEW_ONLY", "SCOPE_NOT_REVIEW_ONLY")
    _require(data.get("g6_status") == "HOLD", "G6_NOT_VERIFIABLE")
    batch_id = data.get("batch_id")
    _require(
        isinstance(batch_id, str)
        and re.fullmatch(r"[A-Za-z0-9._-]{1,80}", batch_id) is not None,
        "INVALID_BATCH_ID",
    )
    records = data.get("records")
    _require(isinstance(records, list) and 1 <= len(records) <= MAX_RECORDS,
             "INVALID_RECORD_COUNT")
    seen_titles: set[str] = set()
    seen_sources: set[str] = set()
    real_count = 0
    demo_count = 0
    for record in records:
        kind, normalized_title = _validate_record(record)
        _require(normalized_title not in seen_titles, "DUPLICATE_TITLE")
        seen_titles.add(normalized_title)
        if kind == "REVIEWED_REAL":
            real_count += 1
            source_url = record["source_url"]
            _require(source_url not in seen_sources, "DUPLICATE_SOURCE_URL")
            seen_sources.add(source_url)
        else:
            demo_count += 1
    return {
        "status": "REVIEW_ONLY",
        "batch_id": batch_id,
        "real_candidates": real_count,
        "demo_candidates": demo_count,
        "authorized_to_publish": False,
        "g4_evidence_authenticity": "NOT_VERIFIED",
        "g6_approval": "HOLD",
        "database_identity": "NOT_CHECKED",
        "database_connections": 0,
        "database_writes": 0,
    }


def check_file(path: Path) -> dict[str, object]:
    _require(path.is_file(), "INPUT_NOT_FOUND")
    _require(path.stat().st_size <= MAX_BYTES, "INPUT_TOO_LARGE")
    try:
        data = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightBlocked("INVALID_JSON") from exc
    return inspect_manifest(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B-Lite read-only candidate preflight")
    parser.add_argument("--input", required=True, type=Path, help="JSON manifest path")
    args = parser.parse_args(argv)
    try:
        result = check_file(args.input)
    except (PreflightBlocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, PreflightBlocked) else "INPUT_READ_FAILED"
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "authorized_to_publish": False,
                          "database_connections": 0, "database_writes": 0}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
