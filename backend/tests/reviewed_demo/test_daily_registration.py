"""No MariaDB DML. Small batch validation and SQLite transaction regression."""

from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from sqlalchemy import (
    Column, Integer, MetaData, String, Table, create_engine, select,
)
from sqlalchemy.engine import Connection

from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
from app.services import reviewed_demo_daily_registration as daily


def batch_for(parent="IT_DIGITAL", child="인공지능"):
    return {
        "input_kind": daily.KIND,
        "approval_scope": "ISOLATED_DEMO_ONLY",
        "expected_target": dict(daily.TARGET),
        "reviewer_alias": "demo-operator",
        "approved_record_count": 1,
        "records": [{
            "title": "합성 테스트 주제",
            "source_title": "테스트 보도자료",
            "source_url": "https://example.org/articles/test-source",
            "parent_code": parent,
            "child_name": child,
            "discovery_method": "MANUAL_WEB_REVIEW",
            "source_review": daily.REVIEW_CHECK,
            "review_note": "합성 검토 결과",
            "operator_approved": True,
        }],
    }


@pytest.mark.parametrize("code", sorted(daily.ALLOWED_ROOTS))
def test_all_six_root_codes(code):
    assert len(daily.validate_batch(batch_for(parent=code))) == 1


@pytest.mark.parametrize("change", [
    lambda b: b.update(approved_record_count=2),
    lambda b: b["records"][0].update(parent_code="UNKNOWN"),
    lambda b: b["records"][0].update(source_review="NOT_REVIEWED"),
    lambda b: b["records"][0].update(operator_approved=False),
    lambda b: b["records"][0].update(review_note=""),
    lambda b: b["records"][0].update(
        source_url="http://localhost/private",
    ),
    lambda b: b["records"][0].update(
        discovery_method="OPENAI_RESPONSES_WEB_SEARCH_LIVE",
    ),
    lambda b: b.update(expected_target={"port": 3309}),
])
def test_bad_inputs_block_without_connecting(change):
    data = batch_for()
    change(data)
    with pytest.raises(daily.RegistrationBlocked):
        daily.validate_batch(data)


def test_in_batch_title_and_url_duplicates():
    data = batch_for()
    second = deepcopy(data["records"][0])
    second["source_url"] = "https://example.org/different"
    data["records"].append(second)
    data["approved_record_count"] = 2
    with pytest.raises(daily.RegistrationBlocked, match="DUPLICATE_IN_BATCH"):
        daily.validate_batch(data)
    second["title"] = "또 다른 제목"
    second["source_url"] = data["records"][0]["source_url"]
    with pytest.raises(daily.RegistrationBlocked, match="DUPLICATE_IN_BATCH"):
        daily.validate_batch(data)


def test_responses_provenance_keeps_original_failure():
    data = batch_for()
    item = data["records"][0]
    item.update(
        discovery_method="OPENAI_RESPONSES_WEB_SEARCH_LIVE",
        original_ai_source_url="https://example.org/original.pdf",
        original_failure="CITATION_URL_MISMATCH",
    )
    assert len(daily.validate_batch(data)) == 1
    item["original_failure"] = "PASS"
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.validate_batch(data)


@pytest.fixture
def isolated_sqlite(monkeypatch):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for model in (Category, Trend, TrendSource, TrendCategoryMap):
        cloned = model.__table__.to_metadata(metadata)
        for column in cloned.primary_key:
            column.type = Integer()
    version = Table(
        "alembic_version", metadata, Column("version_num", String(32)),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(version.insert().values(
            version_num=daily.MIGRATION_VERSION,
        ))
        conn.execute(metadata.tables["categories"].insert(), [
            {
                "category_id": 38, "category_name": "IT/디지털",
                "category_code": "IT_DIGITAL", "parent_id": None,
                "is_active": True, "sort_order": 6,
            },
            {
                "category_id": 44, "category_name": "인공지능",
                "category_code": None, "parent_id": 38,
                "is_active": True, "sort_order": 1,
            },
        ])

    real_sql = Connection.exec_driver_sql

    def simulated_read_only(self, statement, *args, **kwargs):
        # SQLite has no START TRANSACTION READ ONLY; transaction is still real.
        if (statement == "START TRANSACTION READ ONLY"
                and self.engine.dialect.name == "sqlite"):
            return real_sql(self, "SELECT 1")
        return real_sql(self, statement, *args, **kwargs)

    @contextmanager
    def mocked_single_connection_guard(session, **kwargs):
        yield

    monkeypatch.setattr(Connection, "exec_driver_sql", simulated_read_only)
    monkeypatch.setattr(daily, "validate_engine_target", lambda _: None)
    monkeypatch.setattr(
        daily, "_verified_seed_connection", mocked_single_connection_guard,
    )
    monkeypatch.setattr(
        daily.ReviewedDemoRepository, "identity", lambda _: {
            "database_name": daily.TARGET["database"],
            "current_user": daily.TARGET["current_user"],
        },
    )
    monkeypatch.setattr(
        daily.ReviewedDemoRepository, "schema_issues", lambda _: [],
    )
    yield engine, metadata
    engine.dispose()


def test_preflight_does_not_write_and_registration_verifies(isolated_sqlite):
    engine, meta = isolated_sqlite
    data = batch_for()
    result = daily.preflight_batch(engine, data)
    assert result["status"] == "DRY_RUN_READY"
    assert result["dml_executed"] is False
    with engine.connect() as conn:
        assert conn.execute(select(meta.tables["trends"])).all() == []

    candidate = daily.validate_batch(data)[0]
    receipt = daily.register_candidate(engine, candidate)
    assert daily.verify_candidate(
        engine, candidate, receipt,
    )["status"] == "VERIFIED"
    with engine.connect() as conn:
        mapping = conn.execute(
            select(meta.tables["trend_category_map"])
        ).mappings().one()
        assert mapping["category_id"] == 44
        assert mapping["is_primary"] is False
    with pytest.raises(
        daily.RegistrationBlocked, match="DUPLICATE_REGISTRATION_BLOCKED",
    ):
        daily.register_candidate(engine, candidate)


def test_partial_failure_rolls_back_all_tables(isolated_sqlite, monkeypatch):
    engine, meta = isolated_sqlite
    candidate = daily.validate_batch(batch_for())[0]

    def fail(*args, **kwargs):
        raise RuntimeError("private failure")

    monkeypatch.setattr(
        daily.ReviewedDemoRegistrationRepository, "insert_source", fail,
    )
    with pytest.raises(
        daily.RegistrationBlocked, match="TRANSACTION_FAILED_ROLLED_BACK",
    ):
        daily.register_candidate(engine, candidate)
    with engine.connect() as conn:
        for table in ("trends", "trend_sources", "trend_category_map"):
            assert conn.execute(select(meta.tables[table])).all() == []


def test_inactive_child_preflight_reports_position(isolated_sqlite):
    engine, meta = isolated_sqlite
    with engine.begin() as conn:
        conn.execute(meta.tables["categories"].update().where(
            meta.tables["categories"].c.category_id == 44,
        ).values(is_active=False))
    report = daily.preflight_batch(engine, batch_for())
    assert report["status"] == "DRY_RUN_BLOCKED"
    assert report["records"][0]["reason_code"] == (
        "ACTIVE_CHILD_CATEGORY_NOT_UNIQUE"
    )


def test_ambiguous_commit_is_never_retried(isolated_sqlite, monkeypatch):
    engine, _ = isolated_sqlite
    candidate = daily.validate_batch(batch_for())[0]
    attempts = []

    def failed_commit(session):
        attempts.append(1)
        raise RuntimeError("private commit failure")

    monkeypatch.setattr(daily.Session, "commit", failed_commit)
    with pytest.raises(
        daily.RegistrationBlocked, match="COMMIT_OUTCOME_UNKNOWN_NO_RETRY",
    ):
        daily.register_candidate(engine, candidate)
    assert attempts == [1]


def test_wrong_target_rejected_before_db_checkout(monkeypatch):
    engine = MagicMock()

    def reject(_):
        raise daily.RegistrationBlocked("ISOLATED_CONNECTION_REQUIRED")

    monkeypatch.setattr(daily, "validate_engine_target", reject)
    with pytest.raises(
        daily.RegistrationBlocked, match="ISOLATED_CONNECTION_REQUIRED",
    ):
        daily.preflight_batch(engine, batch_for())
    engine.connect.assert_not_called()
