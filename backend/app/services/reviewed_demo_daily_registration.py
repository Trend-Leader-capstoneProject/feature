"""Isolated single-host daily Reviewed JSON registration; no automatic publishing."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.seeds.demo_trends import _verified_seed_connection
from app.external_trends.normalizer import normalize_source_url, normalize_title
from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
from app.repositories.reviewed_demo_registration_repository import (
    ReviewedDemoRegistrationRepository,
)
from app.repositories.reviewed_demo_repository import ReviewedDemoRepository
from app.services.reviewed_demo_registration import (
    TARGET,
    RegistrationBlocked,
    validate_engine_target,
)

ALLOWED_ROOTS = frozenset({
    "FASHION", "BEAUTY", "GAME", "FOOD", "ENTERTAINMENT", "IT_DIGITAL",
})
KIND = "REVIEWED_DEMO_DAILY_BATCH"
REVIEW_CHECK = "URL_TITLE_KEY_CLAIMS_VERIFIED"
MAX_RECORDS = 36
MIGRATION_VERSION = "b7f2c81d9e04"
_PROVENANCE_FIELDS = (
    "original_citation_validation", "original_response_citation_validation",
    "original_response_validation", "search_profile", "candidate_index",
    "search_run_id", "search_evidence_sha256",
)


@dataclass(frozen=True)
class Candidate:
    position: int
    title: object
    url: object
    record: dict
    search_runs: list | None = None


def _filled(value, limit):
    return type(value) is str and bool(value.strip()) and len(value) <= limit


def _validate_responses_provenance(record):
    failure = record.get("original_failure")
    if "original_citation_validation" in record:
        status = record["original_citation_validation"]
        expected = {
            "MATCHED": None, "MISMATCH": "CITATION_URL_MISMATCH",
            "NOT_EVALUATED": "NOT_VALIDATED",
        }
        if (type(status) is not str or status not in expected
                or "original_failure" not in record or failure != expected[status]):
            raise RegistrationBlocked("PROVENANCE_MISMATCH")
    elif type(failure) is not str or failure not in {
        "CITATION_URL_MISMATCH", "NOT_VALIDATED",
    }:
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    enums = {
        "original_response_citation_validation": {
            "MATCHED", "PARTIAL", "MISMATCH", "EMPTY", "NOT_EVALUATED",
        },
        "original_response_validation": {
            "VALID", "PARTIAL", "INVALID", "NOT_EVALUATED",
        },
        "search_profile": ALLOWED_ROOTS,
    }
    for key, allowed in enums.items():
        if key in record and (
            type(record[key]) is not str or record[key] not in allowed
        ):
            raise RegistrationBlocked("PROVENANCE_MISMATCH")
    if "candidate_index" in record and (
        type(record["candidate_index"]) is not int
        or not 0 <= record["candidate_index"] < 3
    ):
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    for key, pattern in (
        ("search_run_id", r"[0-9a-f]{32}"), ("search_evidence_sha256", r"[0-9a-f]{64}"),
    ):
        if key in record and (
            type(record[key]) is not str or re.fullmatch(pattern, record[key]) is None
        ):
            raise RegistrationBlocked("PROVENANCE_MISMATCH")


def _validated_search_runs(data):
    runs = data.get("search_runs", [])
    if type(runs) is not list or len(runs) > MAX_RECORDS:
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    evidence_by_id = {}
    for run in runs:
        if type(run) is not dict or type(run.get("evidence")) is not dict:
            raise RegistrationBlocked("PROVENANCE_MISMATCH")
        run_id, digest = run.get("search_run_id"), run.get("search_evidence_sha256")
        if (type(run_id) is not str or re.fullmatch(r"[0-9a-f]{32}", run_id) is None
                or type(digest) is not str or run_id in evidence_by_id):
            raise RegistrationBlocked("PROVENANCE_MISMATCH")
        try:
            encoded = json.dumps(
                run["evidence"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (ValueError, TypeError, UnicodeError):
            raise RegistrationBlocked("PROVENANCE_MISMATCH") from None
        if hashlib.sha256(encoded).hexdigest() != digest:
            raise RegistrationBlocked("PROVENANCE_MISMATCH")
        evidence_by_id[run_id] = run
    return evidence_by_id


def _validate_run_reference(record, runs):
    reference_fields = ("search_run_id", "search_evidence_sha256", "candidate_index")
    if (record.get("original_citation_validation") == "MATCHED"
            and not all(key in record for key in reference_fields)):
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    if not any(key in record for key in reference_fields):
        return
    run = runs.get(record.get("search_run_id"))
    if (run is None
            or record.get("search_evidence_sha256") != run["search_evidence_sha256"]):
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    evidence = run["evidence"]
    accepted = evidence.get("candidates", [])
    review_only = evidence.get("review_only_candidates", [])
    if type(accepted) is not list or type(review_only) is not list:
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    values = accepted + review_only
    if not all(type(item) is dict for item in values):
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    matches = [item for item in values
               if item.get("candidate_index") == record.get("candidate_index")]
    if len(matches) != 1:
        raise RegistrationBlocked("PROVENANCE_MISMATCH")
    item = matches[0]
    expected = {
        "original_ai_source_url": item.get("source_url"),
        "original_citation_validation": item.get("citation_validation"),
        "original_failure": item.get("rejection_reason"),
        "search_profile": item.get("proposed_category_ref"),
        "original_response_citation_validation": evidence.get("citation_validation"),
        "original_response_validation": evidence.get("response_validation"),
    }
    if (record.get("parent_code") != record.get("search_profile")
            or evidence.get("search_profile") != expected["search_profile"]
            or any(key not in record or record[key] != value
                   for key, value in expected.items())):
        raise RegistrationBlocked("PROVENANCE_MISMATCH")


def validate_batch(data):
    """Validate all records and internal duplicates before any DB connection."""
    if not isinstance(data, dict) or data.get("input_kind") != KIND:
        raise RegistrationBlocked("INVALID_DAILY_INPUT")
    if data.get("approval_scope") != "ISOLATED_DEMO_ONLY":
        raise RegistrationBlocked("APPROVAL_SCOPE_MISMATCH")
    if data.get("expected_target") != TARGET:
        raise RegistrationBlocked("ISOLATED_TARGET_UNCONFIRMED")
    if not _filled(data.get("reviewer_alias"), 100):
        raise RegistrationBlocked("REVIEWER_REQUIRED")
    records = data.get("records")
    count = data.get("approved_record_count")
    if (not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS
            or type(count) is not int or count != len(records)):
        raise RegistrationBlocked("APPROVED_RECORD_COUNT_MISMATCH")

    titles, urls, candidates = set(), set(), []
    runs = _validated_search_runs(data)
    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise RegistrationBlocked("INVALID_DAILY_RECORD")
        for key, length in (
            ("title", 255), ("source_title", 255), ("source_url", 4096),
            ("child_name", 100), ("review_note", 2000),
        ):
            if not _filled(record.get(key), length):
                raise RegistrationBlocked("INVALID_DAILY_RECORD")
        code = record.get("parent_code")
        if (type(code) is not str or code not in ALLOWED_ROOTS
                or record.get("source_review") != REVIEW_CHECK
                or record.get("operator_approved") is not True
                or record.get("platform", "ETC") != "ETC"):
            raise RegistrationBlocked("CATEGORY_OR_REVIEW_NOT_APPROVED")

        method = record.get("discovery_method")
        if method == "MANUAL_WEB_REVIEW":
            if (record.get("original_ai_source_url") is not None
                    or record.get("original_failure") is not None
                    or any(record.get(key) is not None for key in _PROVENANCE_FIELDS)):
                raise RegistrationBlocked("PROVENANCE_MISMATCH")
        elif method == "OPENAI_RESPONSES_WEB_SEARCH_LIVE":
            original = record.get("original_ai_source_url")
            if (not _filled(original, 4096)
                    or normalize_source_url(original) is None):
                raise RegistrationBlocked("PROVENANCE_MISMATCH")
            _validate_responses_provenance(record)
            _validate_run_reference(record, runs)
        else:
            raise RegistrationBlocked("DISCOVERY_METHOD_UNSUPPORTED")
        title = normalize_title(record["title"])
        url = normalize_source_url(record["source_url"])
        if title is None or url is None:
            raise RegistrationBlocked("INVALID_TITLE_OR_SOURCE_URL")
        if title.normalized_title in titles or url.source_key in urls:
            raise RegistrationBlocked("DUPLICATE_IN_BATCH")
        titles.add(title.normalized_title)
        urls.add(url.source_key)
        candidates.append(Candidate(
            position, title, url, record, data.get("search_runs"),
        ))
    return candidates


def _identity_and_schema(connection):
    repo = ReviewedDemoRepository(connection)
    if repo.identity() != {
        "database_name": TARGET["database"],
        "current_user": TARGET["current_user"],
    }:
        raise RegistrationBlocked("DATABASE_IDENTITY_MISMATCH")
    version = connection.execute(text("SELECT version_num FROM alembic_version"))
    if version.scalar_one() != MIGRATION_VERSION or repo.schema_issues():
        raise RegistrationBlocked("SCHEMA_OR_MIGRATION_MISMATCH")
    return repo


def _category_id(connection, candidate, *, lock=False):
    child = Category.__table__.alias("child")
    parent = Category.__table__.alias("parent")
    stmt = select(
        child.c.category_id.label("child_id"),
        parent.c.category_id.label("parent_id"),
        child.c.category_name.label("child_name"),
    ).select_from(child.join(parent, child.c.parent_id == parent.c.category_id))
    stmt = stmt.where(
        parent.c.category_code == candidate.record["parent_code"],
        parent.c.parent_id.is_(None),
        parent.c.is_active.is_(True),
        child.c.is_active.is_(True),
        child.c.category_code.is_(None),
        child.c.category_name == candidate.record["child_name"],
    )
    matches = connection.execute(stmt).mappings().all()
    matches = [
        row for row in matches
        if row["child_name"] == candidate.record["child_name"]
    ]
    if len(matches) != 1:
        raise RegistrationBlocked("ACTIVE_CHILD_CATEGORY_NOT_UNIQUE")
    row = matches[0]
    if lock:
        connection.execute(
            select(Category.__table__.c.category_id).where(
                Category.__table__.c.category_id.in_(
                    (row["parent_id"], row["child_id"])
                ),
            ).with_for_update()
        ).all()
        if _category_id(connection, candidate) != row["child_id"]:
            raise RegistrationBlocked("CATEGORY_CHANGED_DURING_REGISTRATION")
    return row["child_id"]


def _unique_in_database(repository, candidate):
    hits = repository.duplicates(
        title=candidate.title.display_title,
        normalized_title=candidate.title.normalized_title,
        source_key=candidate.url.source_key,
        source_url=candidate.record["source_url"],
        canonical_url=candidate.url.canonical_url,
    )
    if hits["title_trend_ids"] or hits["source_trend_ids"]:
        raise RegistrationBlocked("DUPLICATE_REGISTRATION_BLOCKED")


def preflight_batch(engine, data):
    """Default mode: all-read-only, no DML, detailed per-record blockers."""
    candidates = validate_batch(data)
    validate_engine_target(engine)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("START TRANSACTION READ ONLY")
            try:
                repo = _identity_and_schema(conn)
                records = []
                for item in candidates:
                    try:
                        category_id = _category_id(conn, item)
                        _unique_in_database(repo, item)
                        records.append({
                            "position": item.position,
                            "parent_code": item.record["parent_code"],
                            "child_category_id": category_id,
                            "status": "READY",
                        })
                    except RegistrationBlocked as error:
                        records.append({
                            "position": item.position,
                            "parent_code": item.record["parent_code"],
                            "status": "BLOCKED",
                            "reason_code": str(error),
                        })
            finally:
                conn.rollback()
    except RegistrationBlocked:
        raise
    except Exception:
        raise RegistrationBlocked("PREFLIGHT_DATABASE_INSPECTION_FAILED") from None
    status = ("DRY_RUN_READY" if all(
        row["status"] == "READY" for row in records
    ) else "DRY_RUN_BLOCKED")
    return {
        "status": status, "dml_executed": False,
        "count": len(candidates), "records": records,
    }


def register_candidate(engine, candidate):
    """One record, one atomic transaction; fail closed and never retry."""
    if (not isinstance(candidate, Candidate)
            or type(candidate.position) is not int or candidate.position < 1):
        raise RegistrationBlocked("INVALID_DAILY_CANDIDATE")
    validation_input = {
        "input_kind": KIND,
        "approval_scope": "ISOLATED_DEMO_ONLY",
        "expected_target": dict(TARGET),
        "reviewer_alias": "local-demo-operator",
        "approved_record_count": 1,
        "records": [candidate.record],
    }
    if candidate.search_runs is not None:
        validation_input["search_runs"] = candidate.search_runs
    verified = validate_batch(validation_input)[0]
    if verified.title != candidate.title or verified.url != candidate.url:
        raise RegistrationBlocked("CANDIDATE_CHANGED_AFTER_REVIEW")
    validate_engine_target(engine)
    commit_started = False
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            try:
                with _verified_seed_connection(
                    session, app_env="local",
                    allowed_host=TARGET["host"], allowed_port=TARGET["port"],
                    allowed_database=TARGET["database"],
                    allowed_current_user=TARGET["current_user"],
                ):
                    conn = session.connection()
                    repo = _identity_and_schema(conn)
                    category_id = _category_id(conn, candidate, lock=True)
                    _unique_in_database(repo, candidate)
                    writer = ReviewedDemoRegistrationRepository(conn)
                    instant = datetime.now(UTC).replace(microsecond=0)
                    stored = instant.replace(tzinfo=None)
                    trend_id = writer.insert_trend(
                        title=candidate.title.display_title,
                        normalized_title=candidate.title.normalized_title,
                        registered_at=stored,
                    )
                    source_id = writer.insert_source(
                        trend_id=trend_id, source_key=candidate.url.source_key,
                        source_url=candidate.url.canonical_url,
                        source_title=candidate.record["source_title"],
                        registered_at=stored,
                    )
                    mapping = conn.execute(
                        TrendCategoryMap.__table__.insert().values(
                            trend_id=trend_id, category_id=category_id,
                            is_primary=False, created_at=stored,
                        )
                    )
                    mapping_id = mapping.inserted_primary_key[0]
                    commit_started = True
                    session.commit()
            except Exception:
                session.rollback()
                raise
    except RegistrationBlocked:
        raise
    except Exception:
        raise RegistrationBlocked(
            "COMMIT_OUTCOME_UNKNOWN_NO_RETRY" if commit_started
            else "TRANSACTION_FAILED_ROLLED_BACK"
        ) from None
    digest = hashlib.sha256(json.dumps(
        candidate.record, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "status": "COMMITTED", "position": candidate.position,
        "trend_id": trend_id, "source_id": source_id,
        "trend_category_id": mapping_id, "category_id": category_id,
        "registered_at_utc": instant.isoformat(),
        "record_sha256": digest,
        "discovery_method": candidate.record["discovery_method"],
        "original_ai_source_url": candidate.record.get("original_ai_source_url"),
        "original_failure": candidate.record.get("original_failure"),
        **{key: candidate.record[key] for key in _PROVENANCE_FIELDS
           if key in candidate.record},
        "source_review": candidate.record["source_review"],
        "review_note": candidate.record["review_note"],
        "operator_approved": candidate.record["operator_approved"],
        "approval_scope": "ISOLATED_DEMO_ONLY",
    }


def verify_candidate(engine, candidate, receipt):
    """Post-commit SELECT verification; never resend an INSERT."""
    validate_engine_target(engine)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("START TRANSACTION READ ONLY")
            try:
                _identity_and_schema(conn)
                trend = conn.execute(select(Trend.__table__).where(
                    Trend.__table__.c.trend_id == receipt["trend_id"]
                )).mappings().one()
                source = conn.execute(select(TrendSource.__table__).where(
                    TrendSource.__table__.c.source_id == receipt["source_id"]
                )).mappings().one()
                mapping = conn.execute(select(TrendCategoryMap.__table__).where(
                    TrendCategoryMap.__table__.c.trend_category_id
                    == receipt["trend_category_id"]
                )).mappings().one()
                stored = datetime.fromisoformat(
                    receipt["registered_at_utc"]
                ).replace(tzinfo=None)
                checks = (
                    trend["title"] == candidate.title.display_title,
                    trend["normalized_title"] == candidate.title.normalized_title,
                    trend["status"] == "ACTIVE",
                    trend["summary"] is None, trend["thumbnail_url"] is None,
                    trend["first_collected_at"] == stored,
                    trend["last_collected_at"] == stored,
                    source["collected_at"] == stored,
                    source["trend_id"] == receipt["trend_id"],
                    source["source_url"] == candidate.url.canonical_url,
                    source["source_key"] == candidate.url.source_key,
                    source["source_title"] == candidate.record["source_title"],
                    source["platform"] == "ETC",
                    mapping["trend_id"] == receipt["trend_id"],
                    mapping["category_id"] == receipt["category_id"],
                    not bool(mapping["is_primary"]),
                )
                if not all(checks):
                    raise RegistrationBlocked("POST_COMMIT_VALUE_MISMATCH")
            finally:
                conn.rollback()
    except RegistrationBlocked:
        raise
    except Exception:
        raise RegistrationBlocked("POST_COMMIT_VERIFICATION_FAILED") from None
    return {"status": "VERIFIED", "trend_id": receipt["trend_id"]}
