"""Isolated single-host daily Reviewed JSON registration; no automatic publishing."""

import hashlib
import json
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
    RegistrationBlocked,
    TARGET,
    validate_engine_target,
)

ALLOWED_ROOTS = frozenset({
    "FASHION", "BEAUTY", "GAME", "FOOD", "ENTERTAINMENT", "IT_DIGITAL",
})
KIND = "REVIEWED_DEMO_DAILY_BATCH"
REVIEW_CHECK = "URL_TITLE_KEY_CLAIMS_VERIFIED"
MAX_RECORDS = 36
MIGRATION_VERSION = "b7f2c81d9e04"


@dataclass(frozen=True)
class Candidate:
    position: int
    title: object
    url: object
    record: dict


def _filled(value, limit):
    return type(value) is str and bool(value.strip()) and len(value) <= limit


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
                    or record.get("original_failure") is not None):
                raise RegistrationBlocked("PROVENANCE_MISMATCH")
        elif method == "OPENAI_RESPONSES_WEB_SEARCH_LIVE":
            original = record.get("original_ai_source_url")
            if (not _filled(original, 4096)
                    or normalize_source_url(original) is None
                    or record.get("original_failure") not in {
                        "CITATION_URL_MISMATCH", "NOT_VALIDATED",
                    }):
                raise RegistrationBlocked("PROVENANCE_MISMATCH")
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
        candidates.append(Candidate(position, title, url, record))
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
    verified = validate_batch({
        "input_kind": KIND,
        "approval_scope": "ISOLATED_DEMO_ONLY",
        "expected_target": dict(TARGET),
        "reviewer_alias": "local-demo-operator",
        "approved_record_count": 1,
        "records": [candidate.record],
    })[0]
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
