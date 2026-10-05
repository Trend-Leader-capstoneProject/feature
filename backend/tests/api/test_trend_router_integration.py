from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource

pytestmark = pytest.mark.integration


@pytest.fixture
def client(
    db_session: Session,
) -> Iterator[TestClient]:
    """테스트 Transaction의 DB Session을 실제 API에 주입한다."""

    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[
        get_db
    ] = override_get_db

    try:
        with TestClient(
            application,
        ) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def create_test_trend(
    db_session: Session,
    *,
    normalized_title: str,
    collected_at: datetime,
    status: TrendStatus = TrendStatus.ACTIVE,
) -> Trend:
    trend = Trend(
        title=normalized_title,
        normalized_title=normalized_title,
        summary=None,
        thumbnail_url=None,
        status=status,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add(
        trend,
    )
    db_session.flush()

    return trend


def create_test_source(
    db_session: Session,
    *,
    trend: Trend,
    source_key: str,
    collected_at: datetime,
) -> TrendSource:
    source = TrendSource(
        source_key=source_key,
        source_url=(
            f"https://example.com/{source_key}"
        ),
        source_title=source_key,
        platform=TrendSourcePlatform.ETC,
        collected_at=collected_at,
        external_id=None,
        trend_id=trend.trend_id,
    )

    db_session.add(
        source,
    )
    db_session.flush()

    return source


def test_list_trends_uses_real_database_and_cursor_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    """공개 API가 실제 DB 조회와 Cursor Pagination까지 연결된다."""

    parent = Category(
        category_code=CategoryCode.GAME,
        category_name="API Integration Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add(
        parent,
    )
    db_session.flush()

    child = Category(
        category_code=None,
        category_name="API Integration Child",
        sort_order=1,
        is_active=True,
        parent_id=parent.category_id,
    )

    db_session.add(
        child,
    )
    db_session.flush()

    newest = create_test_trend(
        db_session,
        normalized_title=(
            "trend-api-integration-newest"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            13,
            0,
            0,
        ),
    )

    older = create_test_trend(
        db_session,
        normalized_title=(
            "trend-api-integration-older"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            12,
            0,
            0,
        ),
    )

    hidden = create_test_trend(
        db_session,
        normalized_title=(
            "trend-api-integration-hidden"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            14,
            0,
            0,
        ),
        status=TrendStatus.HIDDEN,
    )

    for trend in (
        newest,
        older,
    ):
        db_session.add(
            TrendCategoryMap(
                trend_id=trend.trend_id,
                category_id=child.category_id,
                is_primary=False,
            )
        )

    db_session.flush()

    old_source = create_test_source(
        db_session,
        trend=newest,
        source_key=(
            "api-integration-source-old"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            12,
            30,
            0,
        ),
    )

    latest_source = create_test_source(
        db_session,
        trend=newest,
        source_key=(
            "api-integration-source-latest"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            13,
            0,
            0,
        ),
    )

    create_test_source(
        db_session,
        trend=older,
        source_key=(
            "api-integration-source-older"
        ),
        collected_at=datetime(
            2026,
            9,
            30,
            12,
            0,
            0,
        ),
    )

    first_response = client.get(
        "/api/trends",
        params={
            "limit": 1,
        },
    )

    assert first_response.status_code == 200

    first_body = first_response.json()

    assert first_body["success"] is True
    assert first_body["statusCode"] == 200
    assert (
        first_body["message"]
        == "전체 트렌드를 조회했습니다."
    )

    assert len(
        first_body["data"]["items"]
    ) == 1

    first_item = (
        first_body["data"]["items"][0]
    )

    assert (
        first_item["last_collected_at"]
        == "2026-09-30T13:00:00Z"
    )

    assert (
        first_item["trend_id"]
        == newest.trend_id
    )
    assert (
        first_item["trend_id"]
        != hidden.trend_id
    )

    assert first_item["categories"] == [
        {
            "category_id": (
                child.category_id
            ),
            "category_name": (
                child.category_name
            ),
            "parent": {
                "category_id": (
                    parent.category_id
                ),
                "category_code": "GAME",
                "category_name": (
                    parent.category_name
                ),
            },
        }
    ]

    assert (
        first_item["latest_source"][
            "source_id"
        ]
        == latest_source.source_id
    )
    assert (
        first_item["latest_source"][
            "source_id"
        ]
        != old_source.source_id
    )

    assert (
        first_body["data"]["has_next"]
        is True
    )

    next_cursor = (
        first_body["data"]["next_cursor"]
    )

    assert isinstance(
        next_cursor,
        str,
    )
    assert next_cursor

    second_response = client.get(
        "/api/trends",
        params={
            "limit": 1,
            "cursor": next_cursor,
        },
    )

    assert second_response.status_code == 200

    second_body = second_response.json()

    assert [
        item["trend_id"]
        for item
        in second_body["data"]["items"]
    ] == [
        older.trend_id,
    ]

    assert (
        second_body["data"]["has_next"]
        is False
    )
    assert (
        second_body["data"]["next_cursor"]
        is None
    )
