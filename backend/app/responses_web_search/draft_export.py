"""Whitelisted unapproved daily drafts, stored once outside Git checkouts."""

import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TextIO
from unicodedata import category
from urllib.parse import unquote
from uuid import uuid4

from .demo_search import PROFILE_SCOPES
from .manual_review import _PRIVATE_TEXT
from .validator import canonical_url

# The approved isolated Daily target. No DB module is imported by search/export.
_TARGET = {
    "host": "127.0.0.1", "port": 3310,
    "database": "trend_leader_demo_review_20261117",
    "current_user": "trend_demo_review@%",
}
_DIAGNOSTICS = {
    "status": {
        "PREVIEW_READY", "PARTIAL_PREVIEW_READY", "NO_VALID_CANDIDATES",
        "EMPTY_RESULT", "INVALID_OR_INCOMPLETE_RESPONSE", "SEARCH_NOT_EXECUTED",
        "UPSTREAM_ERROR", "BLOCKED_CONFIG", "LIVE_NOT_AUTHORIZED",
    },
    "search_execution": {"CONFIRMED", "NOT_CONFIRMED", "UNKNOWN"},
    "response_validation": {"VALID", "PARTIAL", "INVALID", "NOT_EVALUATED"},
    "citation_validation": {"MATCHED", "PARTIAL", "MISMATCH", "EMPTY", "NOT_EVALUATED"},
    "candidate_validation": {"VALID", "PARTIAL", "INVALID", "EMPTY", "NOT_EVALUATED"},
}
_CREDENTIAL = re.compile(
    r"://[^/\s]*@|\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
    r"|\b(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|db[_-]?password"
    r"|database[_-]?url|x[_-]?api[_-]?key)\s*[:=]",
    re.IGNORECASE,
)


class DraftExportError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _text(value, limit, private_texts):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    decoded = unquote(value)
    if (
        any(category(char).startswith("C") for char in decoded)
        or _PRIVATE_TEXT.search(decoded) or _CREDENTIAL.search(decoded)
        or any(secret and secret.casefold() in decoded.casefold()
               for secret in private_texts)
    ):
        raise DraftExportError("UNSAFE_DRAFT_CONTENT")
    return value


def _index(value):
    if type(value) is not int or not 0 <= value < 3:
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    return value


def _code(value, private_texts):
    value = _text(value, 64, private_texts)
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value) is None:
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    return value


def _candidate(item, profile, citation, private_texts):
    if (
        type(item) is not dict or item.get("proposed_category_ref") != profile
        or item.get("citation_validation") != citation
    ):
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    result = {
        "candidate_index": _index(item.get("candidate_index")),
        "citation_validation": citation, "proposed_category_ref": profile,
    }
    for key, limit in (
        ("topic_draft", 255), ("source_url", 4096), ("source_title_reference", 255),
    ):
        result[key] = _text(item.get(key), limit, private_texts)
    if canonical_url(result["source_url"]) is None:
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    if citation == "MISMATCH":
        if item.get("rejection_reason") != "CITATION_URL_MISMATCH":
            raise DraftExportError("INVALID_DRAFT_EVIDENCE")
        result["rejection_reason"] = "CITATION_URL_MISMATCH"
    return result


def build_reviewed_draft(preview, *, profile, run_id, private_texts=()):
    """Hash the exact sanitized evidence retained in this batch; no approval."""
    if (
        type(profile) is not str or profile not in PROFILE_SCOPES
        or type(run_id) is not str or re.fullmatch(r"[0-9a-f]{32}", run_id) is None
        or type(preview) is not dict or preview.get("mode") != "LIVE"
        or preview.get("search_profile") not in (None, profile)
    ):
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    evidence = {"mode": "LIVE", "requested_profile": profile,
                "search_profile": preview.get("search_profile")}
    for key, allowed in _DIAGNOSTICS.items():
        value = preview.get(key)
        if type(value) is not str or value not in allowed:
            raise DraftExportError("INVALID_DRAFT_EVIDENCE")
        evidence[key] = value
    for key in ("request_started_at_utc", "response_received_at_utc"):
        value = preview.get(key)
        if value is not None:
            value = _text(value, 64, private_texts)
            try:
                instant = datetime.fromisoformat(value)
                offset = instant.utcoffset()
                if offset is None or offset.total_seconds() != 0:
                    raise ValueError()
            except ValueError:
                raise DraftExportError("INVALID_DRAFT_EVIDENCE") from None
        evidence[key] = value
    reasons = preview.get("reason_codes", [])
    issues = preview.get("issues", [])
    if type(reasons) is not list or len(reasons) > 16 or type(issues) is not list:
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    if len(issues) > 3 or not all(type(item) is dict for item in issues):
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    evidence["reason_codes"] = [_code(item, private_texts) for item in reasons]
    evidence["issues"] = [{
        "candidate_index": _index(item.get("candidate_index")),
        "code": _code(item.get("code"), private_texts),
    } for item in issues]
    for key, citation in (
        ("candidates", "MATCHED"), ("review_only_candidates", "MISMATCH"),
    ):
        values = preview.get(key, [])
        if type(values) is not list or len(values) > 3:
            raise DraftExportError("INVALID_DRAFT_EVIDENCE")
        evidence[key] = [_candidate(item, profile, citation, private_texts)
                         for item in values]
    candidates = sorted(
        evidence["candidates"] + evidence["review_only_candidates"],
        key=lambda item: item["candidate_index"],
    )
    if (len({item["candidate_index"] for item in candidates}) != len(candidates)
            or (candidates and preview.get("search_profile") != profile)):
        raise DraftExportError("INVALID_DRAFT_EVIDENCE")
    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    records = [{
        "title": item["topic_draft"], "source_title": item["source_title_reference"],
        "source_url": item["source_url"], "parent_code": profile, "child_name": None,
        "discovery_method": "OPENAI_RESPONSES_WEB_SEARCH_LIVE",
        "original_ai_source_url": item["source_url"],
        "original_failure": item.get("rejection_reason"),
        "original_citation_validation": item["citation_validation"],
        "original_response_citation_validation": evidence["citation_validation"],
        "original_response_validation": evidence["response_validation"],
        "search_profile": profile, "candidate_index": item["candidate_index"],
        "search_run_id": run_id, "search_evidence_sha256": digest,
        "source_review": "NOT_REVIEWED", "review_note": None,
        "operator_approved": False,
    } for item in candidates]
    return {
        "input_kind": "REVIEWED_DEMO_DAILY_BATCH",
        "approval_scope": "ISOLATED_DEMO_ONLY", "expected_target": dict(_TARGET),
        "reviewer_alias": None, "approved_record_count": 0, "records": records,
        "search_runs": [{"search_run_id": run_id,
                         "search_evidence_sha256": digest, "evidence": evidence}],
    }


@dataclass
class DraftFile:
    path: Path
    run_id: str
    stream: TextIO = field(repr=False)
    attempted: bool = field(default=False, init=False)

    def save(self, preview, *, profile, private_texts=()):
        if self.attempted:
            raise DraftExportError("DRAFT_ALREADY_WRITTEN")
        self.attempted = True
        batch = build_reviewed_draft(
            preview, profile=profile, run_id=self.run_id, private_texts=private_texts,
        )
        try:
            text = json.dumps(batch, ensure_ascii=False, indent=2,
                              allow_nan=False) + "\n"
            if self.stream.write(text) != len(text):
                raise OSError()
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except (OSError, ValueError):
            raise DraftExportError("DRAFT_WRITE_FAILED_NO_RETRY") from None
        return {
            "draft_file": str(self.path), "search_run_id": self.run_id,
            "search_evidence_sha256": batch["search_runs"][0]["search_evidence_sha256"],
        }


@contextmanager
def reserve_draft(directory):
    """Reserve an exclusive file and check writability before any paid dispatch."""
    try:
        destination = Path(directory).resolve(strict=True)
        repository = Path(__file__).resolve().parents[3]
        if (not destination.is_dir() or destination.is_relative_to(repository)
                or any((parent / ".git").exists()
                       for parent in (destination, *destination.parents))):
            raise ValueError()
    except (OSError, ValueError, TypeError):
        raise DraftExportError("DRAFT_DESTINATION_INVALID") from None
    run_id = uuid4().hex
    path = destination / f"responses_demo_{run_id}.json"
    try:
        stream = path.open("x", encoding="utf-8", newline="\n")
    except OSError:
        raise DraftExportError("DRAFT_DESTINATION_UNAVAILABLE") from None
    try:
        with stream:
            stream.flush()
            os.fsync(stream.fileno())
            yield DraftFile(path=path, run_id=run_id, stream=stream)
    except DraftExportError:
        raise
    except Exception:
        raise DraftExportError("DRAFT_WRITE_FAILED_NO_RETRY") from None
