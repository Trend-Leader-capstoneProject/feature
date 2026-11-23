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
from app.models.db_enums import CategoryCode, TrendSourcePlatform, TrendStatus
from app.models.trend import Trend
from scripts.ap3_writer_transaction import insert_trend_item

pytestmark = pytest.mark.integration

ARTICLE_URL = "https://www.yna.co.kr/view/AKR20261123042700005"
EVENT_TITLE = "지드래곤·김태호 PD '굿데이' 시즌2 제작 확정"
EVENT_SUMMARY = (
    "제작사 TEO가 음악 예능 '굿데이' 시즌2 제작을 발표했습니다."
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


def test_hidden_news_row_is_not_exposed(
    client: TestClient, db_session: Session,
) -> None:
    """A preapproval/HIDDEN record must never leak into public trend listing."""
    observed = datetime(2026, 11, 23, 9, 0, 0)
    hidden = Trend(
        title="SearchApi pending article fact",
        normalized_title="searchapi-contract-pending-article",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.HIDDEN,
        first_collected_at=observed,
        last_collected_at=observed,
        updated_at=None,
    )
    db_session.add(hidden)
    db_session.flush()
    response = client.get("/api/trends")
    assert response.status_code == 200, response.text
    assert all(
        row["trend_id"] != hidden.trend_id
        for row in response.json()["data"]["items"]
    )
