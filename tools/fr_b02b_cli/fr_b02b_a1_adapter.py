"""Read-only A1 v0.2 single-item compatibility inspection.

Contract checked against the *actual* A1_RECONCILE_V02 reconciler provided with
Trend Leader's G5 P1 HOLD gate ZIP. This is still not the authoritative A1
reconciler or a proof of G4 authenticity, rights, observation, or G6 approval.

The original A1 schema intentionally stores content_ref and review_evidence_id
in approvals.records[], NOT in batch.items[]. Never rewrite original inputs.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
import zlib
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

SCHEMA = "A1_RECONCILE_V02"
POLICY = "v0.3_POLICY_CONFIRMED"
CONTENT_KEYS = frozenset({
    "title", "summary", "category_refs", "source_platform", "source_url",
    "source_title", "thumbnail_url",
})
APPROVAL_KEYS = frozenset({
    "trend_ref", "review_evidence_id", "rights_evidence_id",
    "approved_by", "approved_at", "g4_result", "approval_status",
    "risk_class", "rights_checked", "link_checked", "no_reproduction_checked",
    "google_rss_derived", "revoked", "policy_version", "content_ref",
    "source_title_origin", "source_label_evidence_id",
})
APPROVALS_ROOT_KEYS = frozenset({"schema", "policy_version", "records"})
BATCH_ROOT_KEYS = frozenset({
    "schema", "policy_version", "batch_id", "profile", "g6_status", "items",
})
BATCH_ITEM_KEYS = frozenset({"trend_ref", "content", "source_title_origin"})
MAX_FILE_BYTES = 1_048_576
MAX_ARCHIVE_BYTES = 20 * MAX_FILE_BYTES
A1_ZIP_PREFIX = "g5_p1_hold_v01/"
A1_ZIP_APPROVALS = A1_ZIP_PREFIX + "python315_approval_manifest_RECONFIRMED_v02.json"
A1_ZIP_BATCH = A1_ZIP_PREFIX + "python315_batch_candidate_REVIEW_ONLY_v02.json"
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")


class A1InspectionError(ValueError):
    """Stop on an invalid or ineligible input rather than manufacturing evidence."""


def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise A1InspectionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _fail_constant(_value: str) -> None:
    raise A1InspectionError("nonfinite JSON value is not supported")


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise A1InspectionError("expected an ordinary JSON input file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise A1InspectionError("A1 file exceeds 1 MiB limit")
    with path.open("rb") as file:
        raw = file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise A1InspectionError("A1 file exceeds 1 MiB limit")
    return _parse_a1_bytes(raw)


def _parse_a1_bytes(raw: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_strict_json_pairs,
            parse_constant=_fail_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise A1InspectionError("invalid UTF-8 JSON document") from exc
    if not isinstance(obj, dict):
        raise A1InspectionError("A1 JSON root must be an object")
    return obj


def _require_keys(obj: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise A1InspectionError(f"{name}: unexpected or missing fields")
    return obj


def _value_string(value: Any, name: str, max_length: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > max_length
    ):
        raise A1InspectionError(f"invalid {name}")
    if any(ord(c) < 32 for c in value):
        raise A1InspectionError(f"control characters in {name}")
    return value


def _aware_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _valid_content(content: Any, origin: Any, label_evidence: Any) -> dict[str, Any]:
    content = _require_keys(content, CONTENT_KEYS, "A1 content")
    _value_string(content["title"], "content.title", 255)
    _value_string(content["summary"], "content.summary", 10_000)
    refs = content["category_refs"]
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) for x in refs):
        raise A1InspectionError("invalid content.category_refs")
    if len(refs) != len(set(refs)) or any(not x or x != x.strip() or len(x) > 255 for x in refs):
        raise A1InspectionError("invalid/duplicate content.category_refs")
    if content["source_platform"] not in ("GOOGLE", "YOUTUBE", "SNS", "ETC"):
        raise A1InspectionError("invalid content.source_platform")
    url = _value_string(content["source_url"], "content.source_url")
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError as exc:
        raise A1InspectionError("invalid content.source_url HTTPS destination") from exc
    if (
        parts.scheme != "https" or not host or parts.username is not None
        or parts.password is not None or parts.fragment or " " in parts.netloc
    ):
        raise A1InspectionError("invalid content.source_url HTTPS destination")
    if content["thumbnail_url"] is not None:
        raise A1InspectionError("content.thumbnail_url must be null")
    if origin == "NONE":
        if content["source_title"] is not None or label_evidence is not None:
            raise A1InspectionError("invalid NONE provenance")
    elif origin == "EDITORIAL_LABEL":
        title = _value_string(content["source_title"], "content.source_title", 80)
        if "<" in title or ">" in title:
            raise A1InspectionError("HTML brackets in content.source_title")
        _value_string(label_evidence, "source_label_evidence_id", 255)
    else:
        raise A1InspectionError("unsupported source_title_origin")
    return content


def calculate_content_ref(
    trend_ref: str,
    content: dict[str, Any],
    source_title_origin: str,
    source_label_evidence_id: str | None,
) -> str:
    """Recalculate documented A1 v0.2 digest. Not proof of human approval."""
    _value_string(trend_ref, "trend_ref", 255)
    _valid_content(content, source_title_origin, source_label_evidence_id)
    payload = {
        "schema": SCHEMA,
        "policy_version": POLICY,
        "trend_ref": trend_ref,
        "content": content,
        "source_title_origin": source_title_origin,
        "source_label_evidence_id": source_label_evidence_id,
    }
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def inspect_a1_json(approvals: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    """Check the actual A1 v0.2 JSON shape for one eligible review-only item.

    Unlike the original reconciler, excluded items cause this *strict, single-item*
    CLI command to fail closed rather than return an EXCLUDE report.
    """
    approvals = _require_keys(approvals, APPROVALS_ROOT_KEYS, "approvals")
    batch = _require_keys(batch, BATCH_ROOT_KEYS, "batch")
    for obj, name in ((approvals, "approvals"), (batch, "batch")):
        if obj["schema"] != SCHEMA:
            raise A1InspectionError(f"unsupported {name} schema")
        if obj["policy_version"] != POLICY:
            raise A1InspectionError(f"unsupported {name} policy_version")
    if batch["profile"] != "MVP-A":
        raise A1InspectionError("unsupported batch profile")
    _value_string(batch["batch_id"], "batch.batch_id", 255)
    if batch["g6_status"] != "HOLD":
        raise A1InspectionError("G6 status other than HOLD is not accepted by this PoC")
    records = approvals["records"]
    items = batch["items"]
    if not isinstance(records, list) or not records:
        raise A1InspectionError("approvals.records must be nonempty")
    if not isinstance(items, list) or len(items) != 1:
        raise A1InspectionError("this read-only PoC supports exactly one Batch item")
    item = _require_keys(items[0], BATCH_ITEM_KEYS, "batch.items[0]")
    trend_ref = _value_string(item["trend_ref"], "batch.items[0].trend_ref", 255)
    index: dict[str, dict[str, Any]] = {}
    for idx, raw in enumerate(records):
        record = _require_keys(raw, APPROVAL_KEYS, f"approvals.records[{idx}]")
        record_ref = _value_string(record["trend_ref"], "approval.trend_ref", 255)
        if record_ref in index:
            raise A1InspectionError("duplicate approval trend_ref")
        index[record_ref] = record
        if record["policy_version"] != POLICY:
            raise A1InspectionError("approval policy_version mismatch")
        if record["g4_result"] not in ("PASS", "HOLD", "FAIL"):
            raise A1InspectionError("invalid G4 status")
        if record["approval_status"] not in ("APPROVED", "PENDING", "REJECTED"):
            raise A1InspectionError("invalid approval_status")
        if record["risk_class"] not in (
            "GENERAL_ELIGIBLE", "HIGH_RISK", "INSUFFICIENT_EVIDENCE", "NO_PERMISSION"
        ):
            raise A1InspectionError("invalid risk_class")
        for name in (
            "rights_checked", "link_checked", "no_reproduction_checked",
            "google_rss_derived", "revoked",
        ):
            if type(record[name]) is not bool:
                raise A1InspectionError(f"approval.{name} must be boolean")
        if record["source_title_origin"] not in ("NONE", "EDITORIAL_LABEL"):
            raise A1InspectionError("invalid source_title_origin")
        if record["source_label_evidence_id"] is not None:
            _value_string(record["source_label_evidence_id"], "source_label_evidence_id", 255)
        if record["content_ref"] is not None and not isinstance(record["content_ref"], str):
            raise A1InspectionError("invalid approval.content_ref")

    approval = index.get(trend_ref)
    if approval is None:
        raise A1InspectionError("G4_RECORD_MISSING")
    if approval["revoked"]:
        raise A1InspectionError("APPROVAL_REVOKED")
    if approval["risk_class"] != "GENERAL_ELIGIBLE":
        raise A1InspectionError("risk class ineligible")
    if approval["g4_result"] != "PASS" or approval["approval_status"] != "APPROVED":
        raise A1InspectionError("G4_NOT_APPROVED")
    for name in ("review_evidence_id", "rights_evidence_id", "approved_by"):
        _value_string(approval[name], name, 255)
    if not _aware_timestamp(approval["approved_at"]):
        raise A1InspectionError("APPROVAL_EVIDENCE_INCOMPLETE: approved_at")
    if not all(
        approval[name] for name in ("rights_checked", "link_checked", "no_reproduction_checked")
    ):
        raise A1InspectionError("G4_CHECK_INCOMPLETE")
    if approval["google_rss_derived"]:
        raise A1InspectionError("UNAPPROVED_GOOGLE_RSS")
    if approval["source_title_origin"] != item["source_title_origin"]:
        raise A1InspectionError("SOURCE_TITLE_ORIGIN_MISMATCH")
    approved_digest = approval["content_ref"]
    if not isinstance(approved_digest, str) or not SHA256_REF.fullmatch(approved_digest):
        raise A1InspectionError("missing or invalid approval.content_ref")
    calculated = calculate_content_ref(
        trend_ref, item["content"], approval["source_title_origin"],
        approval["source_label_evidence_id"],
    )
    if approved_digest != calculated:
        raise A1InspectionError("CONTENT_CHANGED_REVIEW_REQUIRED: content_ref mismatch")

    return {
        "status": "A1_STRUCTURE_MATCH_REVIEW_ONLY",
        "a1_reconcile_reason": "ELIGIBLE_FOR_REVIEW_ONLY",
        "a1_potentially_eligible": 1,
        "a1_authorized_to_publish": 0,
        "trend_ref": trend_ref,
        "content_ref": approved_digest,
        "review_evidence_id": approval["review_evidence_id"],
        "source_url": item["content"]["source_url"],
        "source_title_origin": approval["source_title_origin"],
        "p4_initial_adapter_source_title_supported": (
            approval["source_title_origin"] == "EDITORIAL_LABEL"
        ),
        "g4_authenticity_verified": False,
        "rights_verified": False,
        "observation_evidence_verified": False,
        "publish_authorization": "NONE",
    }


def inspect_a1_paths(approvals_path: Path, batch_path: Path) -> dict[str, Any]:
    if approvals_path.resolve() == batch_path.resolve():
        raise A1InspectionError("approvals and batch must be separate files")
    return inspect_a1_json(_read_json(approvals_path), _read_json(batch_path))


def inspect_a1_zip(archive_path: Path) -> dict[str, Any]:
    """Inspect the user-provided G5 P1 ZIP directly, without extracting or writing.

    Only the two known A1 v0.2 JSON members are opened. ZIP-contained Python code
    is NOT executed; original manifests, archive, filesystem and DB remain unchanged.
    """
    if archive_path.is_symlink() or not archive_path.is_file():
        raise A1InspectionError("expected an ordinary G5 P1 ZIP file")
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise A1InspectionError("G5 P1 ZIP is too large for this PoC")
    try:
        with ZipFile(archive_path, "r") as archive:
            names = [entry.filename for entry in archive.infolist()]
            if len(names) != len(set(names)):
                raise A1InspectionError("duplicate ZIP member names")
            raw_documents = []
            for name in (A1_ZIP_APPROVALS, A1_ZIP_BATCH):
                try:
                    info = archive.getinfo(name)
                except KeyError as exc:
                    raise A1InspectionError(f"required A1 ZIP member not found: {name}") from exc
                if info.is_dir() or info.file_size > MAX_FILE_BYTES:
                    raise A1InspectionError("invalid or oversized A1 ZIP member")
                with archive.open(info) as stream:
                    raw = stream.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES:
                    raise A1InspectionError("oversized A1 ZIP member")
                raw_documents.append(_parse_a1_bytes(raw))
    except (BadZipFile, EOFError, NotImplementedError) as exc:
        raise A1InspectionError("invalid or unsupported G5 P1 ZIP") from exc
    return inspect_a1_json(raw_documents[0], raw_documents[1])


@dataclass(frozen=True)
class A1Snapshot:
    """Validated display values bound to one immutable archive byte snapshot."""

    archive_bytes: bytes
    trend_ref: str
    content_ref: str
    review_evidence_id: str
    source_url: str
    source_title_origin: str
    title: str
    summary: str
    source_title: str | None


def read_a1_archive(archive_path: Path) -> bytes:
    """Bounded read; reject symlink/reparse ancestors before following a path."""
    if ".." in archive_path.parts:
        raise A1InspectionError("ambiguous archive path")
    path = archive_path.absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise A1InspectionError("archive reparse paths are not supported")
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARCHIVE_BYTES:
        raise A1InspectionError("invalid or oversized A1 archive")
    with path.open("rb") as file:
        raw = file.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise A1InspectionError("oversized A1 archive")
    return raw


def load_a1_snapshot(archive_path: Path) -> A1Snapshot:
    """Read two known JSON members from the SAME bytes used for the ZIP digest.

    Existing inspect commands and their output remain unchanged. This API does
    not authenticate approvals, execute ZIP code, or modify the original A1 hash.
    """
    raw = read_a1_archive(archive_path)
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise A1InspectionError("duplicate ZIP member names")
            documents = []
            for name in (A1_ZIP_APPROVALS, A1_ZIP_BATCH):
                info = archive.getinfo(name)
                if info.is_dir() or info.file_size > MAX_FILE_BYTES:
                    raise A1InspectionError("invalid or oversized A1 ZIP member")
                with archive.open(info) as stream:
                    member = stream.read(MAX_FILE_BYTES + 1)
                if len(member) > MAX_FILE_BYTES:
                    raise A1InspectionError("oversized A1 ZIP member")
                documents.append(_parse_a1_bytes(member))
    except A1InspectionError as exc:
        # The legacy parser includes the duplicate key in its diagnostic. Do
        # not echo untrusted terminal controls through the new observation CLI.
        if str(exc).startswith("duplicate JSON key:"):
            raise A1InspectionError("duplicate JSON key in A1 input") from exc
        raise
    except (BadZipFile, EOFError, NotImplementedError, KeyError, RuntimeError, zlib.error) as exc:
        raise A1InspectionError("invalid or unsupported A1 ZIP") from exc
    result = inspect_a1_json(documents[0], documents[1])
    content = documents[1]["items"][0]["content"]
    return A1Snapshot(
        archive_bytes=raw,
        trend_ref=result["trend_ref"],
        content_ref=result["content_ref"],
        review_evidence_id=result["review_evidence_id"],
        source_url=result["source_url"],
        source_title_origin=result["source_title_origin"],
        title=content["title"],
        summary=content["summary"],
        source_title=content["source_title"],
    )
