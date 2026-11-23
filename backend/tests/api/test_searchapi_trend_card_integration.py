"""Existing API contract for an independently approved SearchApi news row.

This test deliberately inserts an isolated approved-shaped row through ORM
fixtures; it does NOT ingest a live SearchApi response, approve publication,
run the operational Writer, or modify the operational DB/Journal/Timer.
"""

from collections.abc import Iterator
from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import CategoryCode
from app.trend_collection.searchapi_evidence import (
    CrossSourceReview,
    ProposedFact,
    build_review_event_identity,
)
from scripts.ap3_writer_transaction import insert_trend_item
from scripts.run_auto_supply import inspect_snapshot

pytestmark = pytest.mark.integration

ARTICLE_URL = "https://www.yna.co.kr/view/AKR20261123042700005"
EVENT_TITLE = "'굿데이' 시즌2, 2027년 상반기 공개 계획 발표"
EVENT_SUMMARY = (
    "제작사 TEO가 '굿데이' 시즌2의 2027년 상반기 공개 계획을 알렸습니다."
)
# Fixed test-only identity; this is not a validated production event ID.
TEST_EXTERNAL_ID = "test-only-searchapi-good-day-20261123"


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_existing_trend_api_renders_approved_shaped_news_row(
    client: TestClient, db_session: Session,
) -> None:
    """Actual DB IDs and existing /api/trends contract; no mocked API."""
    parent = Category(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="SearchApi Contract Entertainment",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add(parent)
    db_session.flush()

    child = Category(
        category_code=None,
        category_name="SearchApi Contract Variety",
        sort_order=1,
        is_active=True,
        parent_id=parent.category_id,
    )
    db_session.add(child)
    db_session.flush()

    observed = datetime(2026, 11, 23, 9, 0, 0)
    # Exercise the same SQL insert path used by the operational Writer,
    # but only inside the rollback-protected integration DB fixture.
    row = SimpleNamespace(
        title=EVENT_TITLE,
        normalized_title="searchapi-contract-good-day-season2-20261123",
        source_key=sha256(
            f"ETC:{TEST_EXTERNAL_ID}".encode("utf-8")
        ).hexdigest(),
        source_url=ARTICLE_URL,
        external_id=TEST_EXTERNAL_ID,
        platform="ETC",
    )
    trend_id = insert_trend_item(
        db_session.connection(),
        row,
        category_id=child.category_id,
        collected_at=observed,
        summary=EVENT_SUMMARY,
        is_primary=True,
        status="ACTIVE",
        platform="ETC",
    )
    source_id = db_session.execute(
        text("SELECT source_id FROM trend_sources WHERE trend_id = :id"),
        {"id": trend_id},
    ).scalar_one()
    # Confirm the same identity is observed as duplicate by the real Writer
    # inspector, rather than incorrectly proposing a second insert.
    assert inspect_snapshot(db_session.connection(), row) == (
        "SKIP_EXISTING_RELEASE"
    )

    response = client.get("/api/trends", params={"category_id": child.category_id})
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    card = next(item for item in items if item["trend_id"] == trend_id)
    assert card["title"] == EVENT_TITLE
    assert card["summary"] == EVENT_SUMMARY
    assert card["thumbnail_url"] is None
    assert card["latest_source"] == {
        "source_id": source_id,
        "platform": "ETC",
        "source_title": None,
        "source_url": ARTICLE_URL,
    }
    assert card["categories"] == [{
        "category_id": child.category_id,
        "category_name": child.category_name,
        "parent": {
            "category_id": parent.category_id,
            "category_name": parent.category_name,
            "category_code": "ENTERTAINMENT",
        },
    }]


def test_reviewed_event_identity_uses_writer_dedupe_but_stays_hidden(
    client: TestClient, db_session: Session,
) -> None:
    """Review-only evidence can never imply ACTIVE publication authorization."""
    from app.trend_collection.freshness_policy import validate_snapshot_freshness
    from app.trend_collection.supply_adapter import SupplyBlocked

    # Synthetic review proof: this is NOT live original-page verification.
    fact = ProposedFact(
        "good-day-2-2027-h1-announcement",
        "ENTERTAINMENT",
        (("굿데이",), ("시즌2",)),
    )
    review = CrossSourceReview(
        status="REVIEW_REQUIRED",
        reason="TWO_ARTICLE_BODIES_CONTAIN_ASSERTIONS_NOT_INDEPENDENT_PROOF",
        urls=(
            ARTICLE_URL,
            "https://mobile.newsis.com/view/NISX20261123_0003878761",
        ),
        evidence_ref=sha256(b"test-only-article-evidence").hexdigest(),
    )
    identity = build_review_event_identity(fact, review)
    assert identity is not None
    assert identity.proposed_status == "HIDDEN"
    assert identity.publish_authorization == "NONE"
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_TYPE_NOT_SUPPORTED"):
        validate_snapshot_freshness(object(), identity, datetime.now().astimezone())

    parent = Category(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="SearchApi Review-Only Parent",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add(parent)
    db_session.flush()
    child = Category(
        category_code=None,
        category_name="SearchApi Review-Only Child",
        sort_order=1,
        is_active=True,
        parent_id=parent.category_id,
    )
    db_session.add(child)
    db_session.flush()

    # Reuse the common Writer DML inside a rollback-isolated test database.
    # Operational run_writer() is not invoked; an unapproved review item
    # must never reach the ACTIVE publication path.
    row = SimpleNamespace(
        title="SearchApi pending article review",
        normalized_title="searchapi-review-only-good-day-2027",
        external_id=identity.external_id,
        source_key=identity.source_key,
        source_url=identity.source_url,
        platform="ETC",
    )
    trend_id = insert_trend_item(
        db_session.connection(),
        row,
        category_id=child.category_id,
        collected_at=datetime(2026, 11, 23, 9, 0, 0),
        summary=None,
        is_primary=True,
        status=identity.proposed_status,
        platform="ETC",
    )
    assert inspect_snapshot(db_session.connection(), row) == (
        "SKIP_EXISTING_RELEASE"
    )
    persisted = db_session.execute(
        text("SELECT status FROM trends WHERE trend_id = :id"),
        {"id": trend_id},
    ).scalar_one()
    assert persisted == "HIDDEN"

    response = client.get("/api/trends")
    assert response.status_code == 200, response.text
    assert all(
        item["trend_id"] != trend_id
        for item in response.json()["data"]["items"]
    )
