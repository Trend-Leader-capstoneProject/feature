"""One specifically approved isolated demo record. No automatic retry or upsert."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.seeds.demo_trends import _verified_seed_connection
from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
from app.repositories.reviewed_demo_registration_repository import (
    ReviewedDemoRegistrationRepository,
)
from app.repositories.reviewed_demo_repository import ReviewedDemoRepository
from app.services.reviewed_demo_preflight import validate_reviewed_input

TARGET = {
    "host": "127.0.0.1", "port": 3310,
    "database": "trend_leader_demo_review_20261117",
    "current_user": "trend_demo_review@%",
}
TITLE = "[DEMO] 2026년 10월 ICT 수출 703.5억 달러, 전년 대비 202% 증가"
SOURCE_TITLE = "2026년 10월 정보통신산업(ICT) 수출입 동향"
SOURCE_URL = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172408/view"
AI_SOURCE_URL = (
    "https://www.motir.go.kr/attach/down/095a2dda9c864e1d90d751f7668a1117/"
    "f604a620244b9bf41395655d434b6bf4"
)


class RegistrationBlocked(ValueError):
    """Fixed reason code only, no DB exception text or credentials."""


def validate_registration(data):
    title, url = validate_reviewed_input(data)
    expected = {
        "title": TITLE, "source_title": SOURCE_TITLE, "source_url": SOURCE_URL,
        "original_ai_source_url": AI_SOURCE_URL, "platform": "ETC",
        "category_id": 44, "expected_target": TARGET,
        "approval_scope": "ISOLATED_DEMO_ONLY", "approved_record_count": 1,
        "discovery_method": "OPENAI_RESPONSES_WEB_SEARCH_LIVE",
        "government_announced_on": "2026-11-15",
        "official_page_registered_on": "2026-11-16",
    }
    if any(type(data.get(key)) is not type(value) or data[key] != value
           for key, value in expected.items()):
        raise RegistrationBlocked("APPROVED_RECORD_MISMATCH")
    if data.get("review_policy") == "ISOLATED_DEMO_OPERATOR_APPROVAL":
        if (data["reviewer"] != "trend-leader-demo-operator"
                or data.get("operator_approved") is not True):
            raise RegistrationBlocked("OPERATOR_APPROVAL_REQUIRED")
        verification = data.get("official_page_verification", {})
        if not isinstance(verification, dict) or any(
            verification.get(key) is not True
            for key in ("accessible", "title_matches", "dates_match", "figures_match")
        ):
            raise RegistrationBlocked("OFFICIAL_PAGE_VERIFICATION_REQUIRED")
        timestamp = data.get("operator_approved_at")
        timestamp_error = "ACTUAL_APPROVAL_TIME_REQUIRED"
    else:
        if (data["reviewer"] == "USER_CONFIRMED_IN_CHAT"
                or data.get("review_confirmed") is not True):
            raise RegistrationBlocked("OPERATOR_REVIEW_REQUIRED")
        timestamp = data.get("reviewed_at")
        timestamp_error = "ACTUAL_REVIEW_TIME_REQUIRED"
    try:
        recorded_at = datetime.fromisoformat(timestamp)
        if recorded_at.tzinfo is None or recorded_at > datetime.now(UTC):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise RegistrationBlocked(timestamp_error) from None
    return title, url


def validate_engine_target(engine):
    url = engine.url
    if (
        url.drivername != "mysql+pymysql" or url.host != TARGET["host"]
        or url.port != TARGET["port"] or url.database != TARGET["database"]
        or url.username != "trend_demo_review" or set(url.query) - {"charset"}
    ):
        raise RegistrationBlocked("ISOLATED_CONNECTION_REQUIRED")


def registration_checks(connection, data, title, url):
    validate_registration(data)
    repository = ReviewedDemoRepository(connection)
    identity = repository.identity()
    if identity != {"database_name": TARGET["database"],
                    "current_user": TARGET["current_user"]}:
        raise RegistrationBlocked("DATABASE_IDENTITY_MISMATCH")
    version = connection.execute(text("SELECT version_num FROM alembic_version"))
    if version.scalar_one() != "b7f2c81d9e04" or repository.schema_issues():
        raise RegistrationBlocked("SCHEMA_OR_MIGRATION_MISMATCH")
    connection.execute(select(Category.__table__.c.category_id).where(
        Category.__table__.c.category_id.in_((38, 44)),
    ).with_for_update())
    selected = [row for row in repository.categories()
                if row["category_id"] == 44 and row["parent_id"] == 38
                and row["category_name"] == "기타"
                and row["category_code"] == "IT_DIGITAL"]
    if len(selected) != 1:
        raise RegistrationBlocked("APPROVED_CATEGORY_MISMATCH")
    duplicates = repository.duplicates(
        title=title.display_title, normalized_title=title.normalized_title,
        source_key=url.source_key, source_url=data["source_url"],
        canonical_url=url.canonical_url,
    )
    if duplicates["title_trend_ids"] or duplicates["source_trend_ids"]:
        raise RegistrationBlocked("DUPLICATE_REGISTRATION_BLOCKED")


def register_one(engine, data):
    """Revalidate and insert on one guarded Session connection, then commit once."""
    data = deepcopy(data)
    title, url = validate_registration(data)
    digest = hashlib.sha256(json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    validate_engine_target(engine)  # Reject before opening a write-capable connection.
    commit_started = False
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            try:
                with _verified_seed_connection(
                    session, app_env="local", allowed_host=TARGET["host"],
                    allowed_port=TARGET["port"], allowed_database=TARGET["database"],
                    allowed_current_user=TARGET["current_user"],
                ):
                    connection = session.connection()
                    registration_checks(connection, data, title, url)
                    writer = ReviewedDemoRegistrationRepository(connection)
                    instant = datetime.now(UTC).replace(microsecond=0)
                    stored_time = instant.replace(tzinfo=None)
                    trend_id = writer.insert_trend(
                        title=title.display_title,
                        normalized_title=title.normalized_title,
                        registered_at=stored_time,
                    )
                    source_id = writer.insert_source(
                        trend_id=trend_id, source_key=url.source_key,
                        source_url=url.canonical_url, source_title=data["source_title"],
                        registered_at=stored_time,
                    )
                    map_id = writer.insert_category_map(
                        trend_id=trend_id, registered_at=stored_time,
                    )
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
    return {
        "status": "COMMITTED", "trend_id": trend_id, "source_id": source_id,
        "trend_category_id": map_id, "registered_at_utc": instant.isoformat(),
        "input_sha256": digest, "approval_scope": "ISOLATED_DEMO_ONLY",
        "original_failure": "CITATION_URL_MISMATCH",
    }


def verify_registered(connection, data, result):
    """Read-only values check. The caller retains IDs if verification fails."""
    identity = ReviewedDemoRepository(connection).identity()
    if identity != {"database_name": TARGET["database"],
                    "current_user": TARGET["current_user"]}:
        raise RegistrationBlocked("POST_COMMIT_TARGET_MISMATCH")
    trend = connection.execute(select(Trend.__table__).where(
        Trend.__table__.c.trend_id == result["trend_id"],
    )).mappings().one()
    source = connection.execute(select(TrendSource.__table__).where(
        TrendSource.__table__.c.source_id == result["source_id"],
    )).mappings().one()
    mapping = connection.execute(select(TrendCategoryMap.__table__).where(
        TrendCategoryMap.__table__.c.trend_category_id == result["trend_category_id"],
    )).mappings().one()
    title, url = validate_registration(data)
    instant = datetime.fromisoformat(result["registered_at_utc"]).replace(tzinfo=None)
    checks = (
        trend["title"] == TITLE, trend["normalized_title"] == title.normalized_title,
        trend["status"] == "ACTIVE", trend["summary"] is None,
        trend["thumbnail_url"] is None, trend["first_collected_at"] == instant,
        trend["last_collected_at"] == instant, source["collected_at"] == instant,
        source["trend_id"] == mapping["trend_id"] == result["trend_id"],
        source["source_url"] == url.canonical_url,
        source["source_key"] == url.source_key,
        source["source_title"] == SOURCE_TITLE, source["platform"] == "ETC",
        mapping["category_id"] == 44, bool(mapping["is_primary"]),
    )
    if not all(checks):
        raise RegistrationBlocked("POST_COMMIT_VALUE_MISMATCH")
    return {"status": "VERIFIED", "trend_id": trend["trend_id"],
            "source_id": source["source_id"],
            "trend_category_id": mapping["trend_category_id"]}
