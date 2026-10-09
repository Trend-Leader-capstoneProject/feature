from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth_dependency import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendStatus,
    UserStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.user import User
from app.models.user_interest_category import UserInterestCategory

pytestmark = pytest.mark.integration


def test_personalized_trends_matches_user_interest_scope(
    db_session: Session,
) -> None:
    """실제 DB에서 사용자의 관심 Child에 매핑된 Trend만 조회한다."""

    # 1. 인증 사용자와 Root Category 생성
    user = User(
        name="Personalized API 통합 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Integration Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    food_root = Category(
        category_code=CategoryCode.FOOD,
        category_name="Personalized Integration Food",
        sort_order=2,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([
        user,
        game_root,
        food_root,
    ])
    db_session.flush()

    # 2. 각 Root의 활성 Child 생성
    game_child = Category(
        category_code=None,
        category_name="Personalized Integration Mobile Game",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    food_child = Category(
        category_code=None,
        category_name="Personalized Integration Dessert",
        sort_order=1,
        is_active=True,
        parent_id=food_root.category_id,
    )

    db_session.add_all([
        game_child,
        food_child,
    ])
    db_session.flush()

    # 3. 사용자는 GAME Root만 관심사로 선택
    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 4. 서로 다른 Child에 매핑할 ACTIVE Trend 생성
    collected_at = datetime(
        2026, 10, 8, 12, 0, 0,
    )

    matching_trend = Trend(
        title="Personalized Integration Matching",
        normalized_title="personalized-integration-matching",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    unrelated_trend = Trend(
        title="Personalized Integration Unrelated",
        normalized_title="personalized-integration-unrelated",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add_all([
        matching_trend,
        unrelated_trend,
    ])
    db_session.flush()

    # 5. Trend와 Child Category 매핑
    db_session.add_all([
        TrendCategoryMap(
            trend_id=matching_trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=unrelated_trend.trend_id,
            category_id=food_child.category_id,
            is_primary=False,
        ),
    ])
    db_session.flush()

    # 6. 실제 Repository를 사용할 FastAPI 애플리케이션 생성
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
            )
    finally:
        application.dependency_overrides.clear()

    # 7. 실제 MariaDB 조회 결과 검증
    assert response.status_code == 200, response.text

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200

    assert [
        item["trend_id"]
        for item in body["data"]["items"]
    ] == [
        matching_trend.trend_id,
    ]

    assert body["data"]["has_next"] is False
    assert body["data"]["next_cursor"] is None


def test_personalized_trends_excludes_hidden_trends(
    db_session: Session,
) -> None:
    """관심 Category에 일치해도 HIDDEN Trend는 제외한다."""

    # 1. 사용자와 관심 Root 생성
    user = User(
        name="Personalized Hidden 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Hidden Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Hidden Mobile Game",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add(game_child)
    db_session.flush()

    # 2. GAME Root를 관심사로 등록
    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 3. 동일한 관심 Child에 연결할 Trend 생성
    active_time = datetime(2026, 10, 8, 12, 0, 0)
    hidden_time = datetime(2026, 10, 8, 13, 0, 0)

    active_trend = Trend(
        title="Personalized Hidden Test Active",
        normalized_title="personalized-hidden-test-active",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=active_time,
        last_collected_at=active_time,
        updated_at=None,
    )

    hidden_trend = Trend(
        title="Personalized Hidden Test Hidden",
        normalized_title="personalized-hidden-test-hidden",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.HIDDEN,
        first_collected_at=hidden_time,
        last_collected_at=hidden_time,
        updated_at=None,
    )

    db_session.add_all([active_trend, hidden_trend])
    db_session.flush()

    # 4. 두 Trend를 동일한 Child에 매핑
    db_session.add_all([
        TrendCategoryMap(
            trend_id=active_trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=hidden_trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
    ])

    db_session.flush()

    # 5. 실제 Repository를 사용하는 API 호출
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
            )
    finally:
        application.dependency_overrides.clear()

    # 6. 응답에는 ACTIVE Trend만 존재해야 한다.
    assert response.status_code == 200, response.text

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200

    returned_trend_ids = [
        item["trend_id"]
        for item in body["data"]["items"]
    ]

    assert returned_trend_ids == [
        active_trend.trend_id,
    ]

    assert hidden_trend.trend_id not in returned_trend_ids


def test_personalized_trends_deduplicates_multi_category_matches(
    db_session: Session,
) -> None:
    """여러 Child에 매핑된 Trend도 한 번만 반환한다."""

    # 1. 테스트 사용자와 관심 Root
    user = User(
        name="Personalized Duplicate 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Duplicate Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    # 2. 동일 Root 아래 활성 Child 두 개
    mobile_game = Category(
        category_code=None,
        category_name="Personalized Duplicate Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    pc_game = Category(
        category_code=None,
        category_name="Personalized Duplicate PC",
        sort_order=2,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add_all([mobile_game, pc_game])
    db_session.flush()

    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 3. 최신 Trend와 그다음 Trend
    newer_time = datetime(2026, 10, 8, 13, 0, 0)
    older_time = datetime(2026, 10, 8, 12, 0, 0)

    newer_trend = Trend(
        title="Personalized Duplicate Newer",
        normalized_title="personalized-duplicate-newer",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=newer_time,
        last_collected_at=newer_time,
        updated_at=None,
    )

    older_trend = Trend(
        title="Personalized Duplicate Older",
        normalized_title="personalized-duplicate-older",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=older_time,
        last_collected_at=older_time,
        updated_at=None,
    )

    db_session.add_all([newer_trend, older_trend])
    db_session.flush()

    # 4. 최신 Trend는 Child 두 개에 중복 매칭된다.
    db_session.add_all([
        TrendCategoryMap(
            trend_id=newer_trend.trend_id,
            category_id=mobile_game.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=newer_trend.trend_id,
            category_id=pc_game.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=older_trend.trend_id,
            category_id=mobile_game.category_id,
            is_primary=False,
        ),
    ])

    db_session.flush()

    # 5. 실제 MariaDB를 이용하는 API 호출
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
                params={"limit": 2},
            )
    finally:
        application.dependency_overrides.clear()

    # 6. Trend 단위로 중복 제거된 조회 결과
    assert response.status_code == 200, response.text

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200

    returned_trend_ids = [
        item["trend_id"]
        for item in body["data"]["items"]
    ]

    assert returned_trend_ids == [
        newer_trend.trend_id,
        older_trend.trend_id,
    ]

    assert len(returned_trend_ids) == 2
    assert len(set(returned_trend_ids)) == 2

    assert body["data"]["has_next"] is False
    assert body["data"]["next_cursor"] is None


def test_personalized_trends_cursor_uses_trend_id_tie_breaker(
    db_session: Session,
) -> None:
    """수집 시각이 같으면 trend_id 역순으로 페이지를 이동한다."""

    # 1. 사용자 및 관심 Category 생성
    user = User(
        name="Personalized Cursor 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Cursor Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Cursor Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add(game_child)
    db_session.flush()

    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 2. 수집 시각이 동일한 Trend 세 개 생성
    collected_at = datetime(2026, 10, 8, 13, 0, 0)

    trends = [
        Trend(
            title=f"Personalized Cursor Trend {index}",
            normalized_title=f"personalized-cursor-tie-{index}",
            summary=None,
            thumbnail_url=None,
            status=TrendStatus.ACTIVE,
            first_collected_at=collected_at,
            last_collected_at=collected_at,
            updated_at=None,
        )
        for index in range(3)
    ]

    db_session.add_all(trends)
    db_session.flush()

    assert (
        trends[2].trend_id
        > trends[1].trend_id
        > trends[0].trend_id
    )

    # 3. 모든 Trend를 동일한 관심 Child에 연결
    db_session.add_all([
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        )
        for trend in trends
    ])

    db_session.flush()

    # 4. 실제 MariaDB Repository를 사용하는 API
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    returned_ids: list[int] = []
    cursor: str | None = None

    try:
        with TestClient(application) as client:
            # limit=1로 총 3페이지 조회
            for page_index in range(3):
                params: dict[str, int | str] = {
                    "limit": 1,
                }

                if cursor is not None:
                    params["cursor"] = cursor

                response = client.get(
                    "/api/trends/personalized",
                    params=params,
                )

                assert response.status_code == 200, response.text

                body = response.json()

                assert body["success"] is True
                assert body["statusCode"] == 200

                items = body["data"]["items"]

                assert len(items) == 1

                returned_ids.append(
                    items[0]["trend_id"],
                )

                has_next = body["data"]["has_next"]
                cursor = body["data"]["next_cursor"]

                if page_index < 2:
                    assert has_next is True
                    assert isinstance(cursor, str)
                    assert cursor
                else:
                    assert has_next is False
                    assert cursor is None

    finally:
        application.dependency_overrides.clear()

    # 5. 동일 시각에서는 trend_id DESC
    assert returned_ids == [
        trends[2].trend_id,
        trends[1].trend_id,
        trends[0].trend_id,
    ]

    # 페이지 이동 중 중복 반환이 없어야 한다.
    assert len(set(returned_ids)) == 3

def test_personalized_trends_cursor_uses_collected_at_boundary(
    db_session: Session,
) -> None:
    """수집 시각이 다른 Trend는 시간 내림차순으로 페이지를 이동한다."""

    # 1. 테스트 사용자 및 관심 Category
    user = User(
        name="Personalized Time Cursor 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Time Cursor Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Time Cursor Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add(game_child)
    db_session.flush()

    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 2. 최신 Trend를 먼저 생성한다.
    newer_time = datetime(2026, 10, 8, 14, 0, 0)
    older_time = datetime(2026, 10, 8, 13, 0, 0)

    newer_trend = Trend(
        title="Personalized Time Cursor Newer",
        normalized_title="personalized-time-cursor-newer",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=newer_time,
        last_collected_at=newer_time,
        updated_at=None,
    )

    older_trend = Trend(
        title="Personalized Time Cursor Older",
        normalized_title="personalized-time-cursor-older",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=older_time,
        last_collected_at=older_time,
        updated_at=None,
    )

    db_session.add_all([
        newer_trend,
        older_trend,
    ])
    db_session.flush()

    # 오래된 Trend의 ID가 더 큰 상황을 보장한다.
    assert older_trend.trend_id > newer_trend.trend_id

    # 3. 두 Trend 모두 동일한 관심 Child에 매핑
    db_session.add_all([
        TrendCategoryMap(
            trend_id=newer_trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=older_trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
    ])
    db_session.flush()

    # 4. 실제 MariaDB를 사용하는 API 연결
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            # 첫 페이지
            first_response = client.get(
                "/api/trends/personalized",
                params={"limit": 1},
            )

            assert first_response.status_code == 200, (
                first_response.text
            )

            first_data = first_response.json()["data"]

            assert [
                item["trend_id"]
                for item in first_data["items"]
            ] == [
                newer_trend.trend_id,
            ]

            assert first_data["has_next"] is True

            cursor = first_data["next_cursor"]

            assert isinstance(cursor, str)
            assert cursor

            # 첫 페이지에서 발급한 Cursor로 다음 페이지 조회
            second_response = client.get(
                "/api/trends/personalized",
                params={
                    "limit": 1,
                    "cursor": cursor,
                },
            )

            assert second_response.status_code == 200, (
                second_response.text
            )

            second_data = second_response.json()["data"]

            assert [
                item["trend_id"]
                for item in second_data["items"]
            ] == [
                older_trend.trend_id,
            ]

            assert second_data["has_next"] is False
            assert second_data["next_cursor"] is None

    finally:
        application.dependency_overrides.clear()
