from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.seeds.category_master import (
    seed_category_master,
)
from app.db.seeds.demo_trends import (
    seed_demo_trends,
)
from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(
    db_session: Session,
) -> Iterator[TestClient]:
    """현재 테스트 Transaction을 실제 API에 연결한다."""

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


def test_demo_seed_returns_twenty_plus_five_active_trends(
    client: TestClient,
    db_session: Session,
) -> None:
    """Demo Seed가 실제 목록 API에서 20 + 5 Pagination을 만든다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    first_response = client.get(
        "/api/trends",
    )

    assert first_response.status_code == 200

    first_data = first_response.json()[
        "data"
    ]

    assert len(
        first_data["items"],
    ) == 20
    assert first_data["has_next"] is True
    assert isinstance(
        first_data["next_cursor"],
        str,
    )

    first_ids = {
        item["trend_id"]
        for item in first_data["items"]
    }

    second_response = client.get(
        "/api/trends",
        params={
            "cursor": first_data[
                "next_cursor"
            ],
        },
    )

    assert second_response.status_code == 200

    second_data = second_response.json()[
        "data"
    ]

    assert len(
        second_data["items"],
    ) == 5
    assert second_data["has_next"] is False
    assert second_data["next_cursor"] is None

    second_ids = {
        item["trend_id"]
        for item in second_data["items"]
    }

    assert first_ids.isdisjoint(
        second_ids,
    )
    assert len(
        first_ids | second_ids,
    ) == 25

    all_titles = [
        item["title"]
        for item in (
            first_data["items"]
            + second_data["items"]
        )
    ]

    assert (
        "[DEMO] 숨김 검증용 트렌드"
        not in all_titles
    )
