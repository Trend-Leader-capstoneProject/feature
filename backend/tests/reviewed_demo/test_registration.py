"""Guard unit tests and real SQLite transaction tests, no MariaDB writes."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
from app.services import reviewed_demo_registration as service


@pytest.fixture
def approved():
    data = json.loads((Path(__file__).parents[2] / "docs" /
                       "reviewed_demo_ict_20261116.json").read_text(encoding="utf-8"))
    data.pop("review_policy", None)
    # Synthetic operator evidence only, never written into the real input.
    data.update(reviewer="fixture-operator", reviewed_at="2026-01-01T10:00:00+09:00",
                review_confirmed=True)
    return data


@pytest.fixture
def sqlite_transaction(monkeypatch):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for model in (Category, Trend, TrendSource, TrendCategoryMap):
        table = model.__table__.to_metadata(metadata)
        # SQLite requires exactly INTEGER for auto-increment PKs.
        for column in table.primary_key:
            column.type = Integer()
    version = Table("alembic_version", metadata, Column("version_num", String(32)))
    metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(version.insert().values(version_num="b7f2c81d9e04"))
        c.execute(metadata.tables["categories"].insert(), [
            {"category_id": 38, "category_name": "IT", "category_code": "IT_DIGITAL",
             "parent_id": None, "is_active": True, "sort_order": 1},
            {"category_id": 44, "category_name": "기타", "category_code": None,
             "parent_id": 38, "is_active": True, "sort_order": 99},
        ])

    @contextmanager
    def isolated_fixture_guard(session, **kwargs):
        yield

    # Only connection/identity/schema guards are substituted. Actual transactions,
    # queries, insert statements, PKs, failures and rollback use SQLAlchemy+SQLite.
    monkeypatch.setattr(service, "validate_engine_target", lambda engine: None)
    monkeypatch.setattr(service, "_verified_seed_connection", isolated_fixture_guard)
    monkeypatch.setattr(service.ReviewedDemoRepository, "identity", lambda self: {
        "database_name": service.TARGET["database"],
        "current_user": service.TARGET["current_user"],
    })
    monkeypatch.setattr(
        service.ReviewedDemoRepository, "schema_issues", lambda self: [],
    )
    yield engine, metadata
    engine.dispose()


def test_transaction_inserts_one_bundle_and_reexecution_blocks(
    sqlite_transaction, approved,
):
    engine, metadata = sqlite_transaction
    result = service.register_one(engine, approved)
    assert result["status"] == "COMMITTED"
    with engine.connect() as c:
        trend = c.execute(select(metadata.tables["trends"])).mappings().one()
        source = c.execute(select(metadata.tables["trend_sources"])).mappings().one()
        mapping = c.execute(select(metadata.tables["trend_category_map"])
                            ).mappings().one()
        assert service.verify_registered(c, approved, result)["status"] == "VERIFIED"
    assert trend["trend_id"] == source["trend_id"] == mapping["trend_id"]
    assert trend["title"] == service.TITLE and trend["status"] == "ACTIVE"
    assert trend["summary"] is None and trend["thumbnail_url"] is None
    assert source["source_url"] == service.SOURCE_URL and source["platform"] == "ETC"
    assert source["source_title"] == service.SOURCE_TITLE
    assert mapping["category_id"] == 44 and mapping["is_primary"] is True
    with pytest.raises(service.RegistrationBlocked,
                       match="DUPLICATE_REGISTRATION_BLOCKED"):
        service.register_one(engine, approved)


def test_partial_insert_failure_rolls_back_every_row(
    sqlite_transaction, approved, monkeypatch,
):
    engine, metadata = sqlite_transaction

    def fail(*args, **kwargs):
        raise RuntimeError("private failure never expose")

    monkeypatch.setattr(
        service.ReviewedDemoRegistrationRepository, "insert_source", fail,
    )
    with pytest.raises(service.RegistrationBlocked,
                       match="TRANSACTION_FAILED_ROLLED_BACK"):
        service.register_one(engine, approved)
    with engine.connect() as c:
        for name in ("trends", "trend_sources", "trend_category_map"):
            assert c.execute(select(metadata.tables[name])).all() == []


@pytest.mark.parametrize("change", [
    {"review_confirmed": False}, {"reviewer": "USER_CONFIRMED_IN_CHAT"},
    {"reviewed_at": None}, {"reviewed_at": "2026-01-01T10:00:00"},
    {"approval_scope": "PRODUCTION"}, {"approved_record_count": 2},
    {"approved_record_count": True}, {"title": "missing demo prefix"},
    {"source_url": service.AI_SOURCE_URL}, {"category_id": 39},
])
def test_missing_review_or_changed_record_never_opens_connection(approved, change):
    approved.update(change)
    engine = MagicMock()
    with pytest.raises(ValueError):
        service.register_one(engine, approved)
    engine.connect.assert_not_called()


@pytest.mark.parametrize("port", [3307, 3308, 3309])
def test_other_database_rejected_before_checkout(approved, port):
    engine = create_engine(
        f"mysql+pymysql://trend_demo_review:synthetic@127.0.0.1:{port}/"
        "trend_leader_demo_review_20261117"
    )
    engine.connect = MagicMock(side_effect=AssertionError("checkout prohibited"))
    with pytest.raises(service.RegistrationBlocked,
                       match="ISOLATED_CONNECTION_REQUIRED"):
        service.register_one(engine, approved)
    engine.connect.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize("case", ["version", "category", "identity", "schema"])
def test_same_transaction_checks_block_before_insert(
    sqlite_transaction, approved, monkeypatch, case,
):
    engine, metadata = sqlite_transaction
    if case == "version":
        with engine.begin() as c:
            c.execute(metadata.tables["alembic_version"].update().values(
                version_num="wrong",
            ))
    elif case == "category":
        with engine.begin() as c:
            c.execute(metadata.tables["categories"].update().where(
                metadata.tables["categories"].c.category_id == 44,
            ).values(is_active=False))
    elif case == "identity":
        monkeypatch.setattr(service.ReviewedDemoRepository, "identity", lambda self: {
            "database_name": "trend_leader", "current_user": "wrong@%",
        })
    else:
        monkeypatch.setattr(service.ReviewedDemoRepository, "schema_issues",
                            lambda self: [{"code": "COLUMN_MISSING"}])
    with pytest.raises(service.RegistrationBlocked):
        service.register_one(engine, approved)
    with engine.connect() as c:
        assert c.execute(select(metadata.tables["trends"])).all() == []


def test_uncertain_commit_has_one_attempt_and_no_retry(
    sqlite_transaction, approved, monkeypatch,
):
    engine, _ = sqlite_transaction
    attempts = []

    def failed_commit(session):
        attempts.append("commit")
        raise RuntimeError("private commit failure")

    monkeypatch.setattr(service.Session, "commit", failed_commit)
    with pytest.raises(service.RegistrationBlocked,
                       match="COMMIT_OUTCOME_UNKNOWN_NO_RETRY"):
        service.register_one(engine, approved)
    assert attempts == ["commit"]


@pytest.mark.parametrize("case", ["approved", "no-approval", "no-time", "no-page"])
def test_isolated_operator_policy_preserves_unknown_human_review(approved, case):
    approved.update(
        review_policy="ISOLATED_DEMO_OPERATOR_APPROVAL",
        reviewer="trend-leader-demo-operator", reviewed_at=None,
        review_confirmed=False, operator_approved=True,
        operator_approved_at="2026-01-01T19:00:00+09:00",
        official_page_verification={key: True for key in (
            "accessible", "title_matches", "dates_match", "figures_match",
        )},
    )
    if case == "no-approval":
        approved["operator_approved"] = False
    elif case == "no-time":
        approved["operator_approved_at"] = None
    elif case == "no-page":
        approved["official_page_verification"]["figures_match"] = False
    if case == "approved":
        service.validate_registration(approved)
        assert approved["reviewed_at"] is None
        assert approved["review_confirmed"] is False
    else:
        with pytest.raises(service.RegistrationBlocked):
            service.validate_registration(approved)
