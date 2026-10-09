from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.dependencies.auth_dependency import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
    UserStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
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


def test_personalized_trends_returns_latest_source_by_collected_at(
    db_session: Session,
) -> None:
    """실제 DB에서 Trend의 가장 최근 Source를 응답에 연결한다."""

    # 1. 사용자와 관심 Category 생성
    user = User(
        name="Personalized Source 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Source Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Source Mobile",
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

    # 2. 관심 Category에 매핑할 Trend 생성
    collected_at = datetime(2026, 10, 9, 15, 0, 0)

    trend = Trend(
        title="Personalized Source Selection",
        normalized_title="personalized-source-selection",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add(trend)
    db_session.flush()

    db_session.add(
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        )
    )

    # 3. 최신 Source를 먼저 저장
    latest_source = TrendSource(
        source_key="a" * 64,
        source_url="https://example.com/latest",
        source_title="최신 Source",
        platform=TrendSourcePlatform.YOUTUBE,
        collected_at=datetime(2026, 10, 9, 14, 0, 0),
        external_id=None,
        trend_id=trend.trend_id,
    )

    db_session.add(latest_source)
    db_session.flush()

    # 4. 오래된 Source를 나중에 저장
    older_source = TrendSource(
        source_key="b" * 64,
        source_url="https://example.com/older",
        source_title="오래된 Source",
        platform=TrendSourcePlatform.GOOGLE,
        collected_at=datetime(2026, 10, 9, 13, 0, 0),
        external_id=None,
        trend_id=trend.trend_id,
    )

    db_session.add(older_source)
    db_session.flush()

    # 최신 Source의 ID가 더 작도록 보장
    assert latest_source.source_id < older_source.source_id

    # 5. 실제 MariaDB를 사용하는 Personalized API 호출
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

    # 6. 가장 최근 수집된 Source가 반환되는지 확인
    assert response.status_code == 200, response.text

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200

    items = body["data"]["items"]

    assert len(items) == 1
    assert items[0]["trend_id"] == trend.trend_id

    assert items[0]["latest_source"] == {
        "source_id": latest_source.source_id,
        "platform": "YOUTUBE",
        "source_title": "최신 Source",
        "source_url": "https://example.com/latest",
    }


def test_personalized_trends_returns_all_mapped_categories(
    db_session: Session,
) -> None:
    """관심사로 검색된 Trend의 전체 Category를 반환한다."""

    # 1. 사용자와 대분류 생성
    user = User(
        name="Personalized Category 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Category Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    food_root = Category(
        category_code=CategoryCode.FOOD,
        category_name="Personalized Category Food",
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

    # 2. 각각의 활성 Child 생성
    game_child = Category(
        category_code=None,
        category_name="Personalized Category Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    food_child = Category(
        category_code=None,
        category_name="Personalized Category Dessert",
        sort_order=1,
        is_active=True,
        parent_id=food_root.category_id,
    )

    db_session.add_all([
        game_child,
        food_child,
    ])
    db_session.flush()

    # 3. 사용자는 GAME Root만 선택
    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    # 4. 두 Child에 모두 매핑할 Trend 생성
    collected_at = datetime(2026, 10, 9, 14, 0, 0)

    trend = Trend(
        title="Personalized Multiple Category",
        normalized_title="personalized-multiple-category",
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add(trend)
    db_session.flush()

    db_session.add_all([
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        ),
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=food_child.category_id,
            is_primary=False,
        ),
    ])
    db_session.flush()

    # 5. 실제 DB를 사용하는 Personalized API 호출
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

    # 6. 실제 응답 검증
    assert response.status_code == 200, response.text

    body = response.json()

    assert body["success"] is True

    items = body["data"]["items"]

    assert len(items) == 1
    assert items[0]["trend_id"] == trend.trend_id

    # GAME만 선택했더라도 FOOD Category도 반환해야 한다.
    assert items[0]["categories"] == [
        {
            "category_id": game_child.category_id,
            "category_name": game_child.category_name,
            "parent": {
                "category_id": game_root.category_id,
                "category_code": "GAME",
                "category_name": game_root.category_name,
            },
        },
        {
            "category_id": food_child.category_id,
            "category_name": food_child.category_name,
            "parent": {
                "category_id": food_root.category_id,
                "category_code": "FOOD",
                "category_name": food_root.category_name,
            },
        },
    ]


# Phase 3-6A: Trend 수가 증가해도 Source 조회는 한 번만 수행한다.
def test_personalized_trends_loads_sources_in_one_batch(
    db_session: Session,
) -> None:
    """Trend가 여러 개여도 Source 조회 SQL은 한 번만 실행한다."""

    user = User(
        name="Personalized Batch 테스트 사용자",
        status=UserStatus.ACTIVE,
    )
    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Batch Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Batch Mobile",
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

    collected_at = datetime(2026, 10, 9, 14, 0, 0)
    trends = [
        Trend(
            title=f"Personalized Batch Trend {index}",
            normalized_title=(
                f"personalized-batch-trend-{index}"
            ),
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

    for index, trend in enumerate(trends):
        db_session.add_all([
            TrendCategoryMap(
                trend_id=trend.trend_id,
                category_id=game_child.category_id,
                is_primary=False,
            ),
            TrendSource(
                source_key=f"{index + 1:064x}",
                source_url=f"https://example.com/batch/{index}",
                source_title=f"Batch Source {index}",
                platform=TrendSourcePlatform.ETC,
                collected_at=collected_at,
                external_id=None,
                trend_id=trend.trend_id,
            ),
        ])
    db_session.flush()

    source_select_statements: list[str] = []

    def record_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized_sql = " ".join(statement.lower().split())
        if (
            normalized_sql.startswith("select")
            and "from trend_sources" in normalized_sql
        ):
            source_select_statements.append(statement)

    connection = db_session.connection()
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            event.listen(
                connection,
                "before_cursor_execute",
                record_sql,
            )
            try:
                response = client.get(
                    "/api/trends/personalized",
                    params={"limit": 3},
                )
            finally:
                event.remove(
                    connection,
                    "before_cursor_execute",
                    record_sql,
                )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) == 3
    assert {item["trend_id"] for item in items} == {
        trend.trend_id for trend in trends
    }
    assert all(item["latest_source"] is not None for item in items)
    assert len(source_select_statements) == 1, source_select_statements


# Phase 3-6B: Trend 수가 증가해도 Category 조회는 한 번만 수행한다.
def test_personalized_trends_loads_categories_in_one_batch(
    db_session: Session,
) -> None:
    """Trend가 여러 개여도 Category 조회 SQL은 한 번만 실행한다."""

    user = User(
        name="Personalized Category Batch 사용자",
        status=UserStatus.ACTIVE,
    )
    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Category Batch Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Category Batch Mobile",
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

    collected_at = datetime(2026, 10, 9, 15, 0, 0)
    trends = [
        Trend(
            title=f"Personalized Category Batch Trend {index}",
            normalized_title=(
                f"personalized-category-batch-trend-{index}"
            ),
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

    db_session.add_all([
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        )
        for trend in trends
    ])
    db_session.flush()

    category_select_statements: list[str] = []
    all_select_statements: list[str] = []

    def record_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized_sql = " ".join(statement.lower().split())
        if not normalized_sql.startswith("select"):
            return

        all_select_statements.append(statement)

        # Trend 페이지의 EXISTS 서브쿼리는 JOIN categories를 사용하지 않는다.
        # Category Batch 조회는 trend_category_map과 categories를 JOIN한다.
        if (
            "from trend_category_map" in normalized_sql
            and "join categories" in normalized_sql
        ):
            category_select_statements.append(statement)

    connection = db_session.connection()
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return user

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            event.listen(
                connection,
                "before_cursor_execute",
                record_sql,
            )
            try:
                response = client.get(
                    "/api/trends/personalized",
                    params={"limit": 3},
                )
            finally:
                event.remove(
                    connection,
                    "before_cursor_execute",
                    record_sql,
                )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) == 3
    assert {item["trend_id"] for item in items} == {
        trend.trend_id for trend in trends
    }

    expected_categories = [
        {
            "category_id": game_child.category_id,
            "category_name": game_child.category_name,
            "parent": {
                "category_id": game_root.category_id,
                "category_code": "GAME",
                "category_name": game_root.category_name,
            },
        },
    ]
    assert all(
        item["categories"] == expected_categories
        for item in items
    )
    assert len(category_select_statements) == 1, (
        "Category Batch SELECT 감지 결과가 1회가 아닙니다.\n"
        f"감지 횟수: {len(category_select_statements)}\n"
        "실제 SELECT SQL:\n"
        + "\n---\n".join(all_select_statements)
    )


def test_personalized_trends_returns_409_when_interests_not_initialized(
    db_session: Session,
) -> None:
    """관심사를 저장하지 않은 사용자는 409를 반환한다."""

    # 1. 관심사 기록이 없는 사용자 생성
    user = User(
        name="Personalized No Interest 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    db_session.add(user)
    db_session.flush()

    # UserInterestCategory는 생성하지 않는다.

    # 2. 실제 MariaDB를 사용하는 API 구성
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

    # 3. Personalized API 호출
    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
            )
    finally:
        application.dependency_overrides.clear()

    # 4. 관심사 미초기화 오류 검증
    assert response.status_code == 409, response.text

    assert response.json() == {
        "success": False,
        "statusCode": 409,
        "message": "저장된 관심사가 없습니다.",
        "data": {
            "reason": "INTERESTS_NOT_INITIALIZED",
        },
    }


def test_personalized_trends_returns_409_when_no_active_child(
    db_session: Session,
) -> None:
    """관심사 Root에 활성 Child가 없으면 409를 반환한다."""

    # 1. 사용자와 활성 Root Category 생성
    user = User(
        name="Personalized Unavailable 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Unavailable Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    # 2. 비활성 Child Category 생성
    inactive_child = Category(
        category_code=None,
        category_name="Personalized Unavailable Mobile",
        sort_order=1,
        is_active=False,
        parent_id=game_root.category_id,
    )

    db_session.add(inactive_child)
    db_session.flush()

    # 3. 사용자는 활성 GAME Root를 관심사로 선택
    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    db_session.flush()

    # 4. 실제 MariaDB Repository를 사용하는 API 구성
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

    # 5. Personalized API 호출
    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
            )
    finally:
        application.dependency_overrides.clear()

    # 6. 유효 Child Scope가 없으므로 409
    assert response.status_code == 409, response.text

    assert response.json() == {
        "success": False,
        "statusCode": 409,
        "message": (
            "현재 관심사로 맞춤 트렌드를 "
            "조회할 수 없습니다."
        ),
        "data": {
            "reason": "INTERESTS_NOT_AVAILABLE",
        },
    }


def test_personalized_trends_rejects_malformed_cursor(
    db_session: Session,
) -> None:
    """잘못된 Personalized Cursor는 실제 DB 경로에서도 400이다."""

    # 1. 정상적인 사용자와 활성 관심 Category 생성
    user = User(
        name="Personalized Invalid Cursor 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Invalid Cursor Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([user, game_root])
    db_session.flush()

    game_child = Category(
        category_code=None,
        category_name="Personalized Invalid Cursor Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add(game_child)
    db_session.flush()

    # 2. 사용자의 관심사는 정상적으로 초기화한다.
    db_session.add(
        UserInterestCategory(
            user_id=user.user_id,
            category_id=game_root.category_id,
        )
    )

    db_session.flush()

    # 3. 실제 MariaDB Repository를 사용하는 API 구성
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

    # 4. 잘못된 Cursor를 전달한다.
    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
                params={
                    "cursor": "invalid-personalized-cursor",
                },
            )
    finally:
        application.dependency_overrides.clear()

    # 5. INVALID_CURSOR 오류 응답 검증
    assert response.status_code == 400, response.text

    assert response.json() == {
        "success": False,
        "statusCode": 400,
        "message": "페이지 정보가 올바르지 않습니다.",
        "data": {
            "reason": "INVALID_CURSOR",
        },
    }


def test_personalized_trends_rejects_cursor_from_another_user(
    db_session: Session,
) -> None:
    """관심사가 같아도 다른 사용자의 Cursor는 거부한다."""

    # 1. 사용자 A와 B 생성
    user_a = User(
        name="Personalized Cursor User A",
        status=UserStatus.ACTIVE,
    )

    user_b = User(
        name="Personalized Cursor User B",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Cross User Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add_all([
        user_a,
        user_b,
        game_root,
    ])
    db_session.flush()

    # 2. 활성 Child 생성
    game_child = Category(
        category_code=None,
        category_name="Personalized Cross User Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    db_session.add(game_child)
    db_session.flush()

    # 3. 두 사용자가 동일한 GAME 관심사를 선택
    db_session.add_all([
        UserInterestCategory(
            user_id=user_a.user_id,
            category_id=game_root.category_id,
        ),
        UserInterestCategory(
            user_id=user_b.user_id,
            category_id=game_root.category_id,
        ),
    ])
    db_session.flush()

    # 4. Cursor를 발급받기 위한 ACTIVE Trend 두 개
    collected_at = datetime(2026, 10, 9, 12, 0, 0)

    trends = [
        Trend(
            title=f"Personalized Cross User Trend {index}",
            normalized_title=(
                f"personalized-cross-user-trend-{index}"
            ),
            summary=None,
            thumbnail_url=None,
            status=TrendStatus.ACTIVE,
            first_collected_at=collected_at,
            last_collected_at=collected_at,
            updated_at=None,
        )
        for index in range(2)
    ]

    db_session.add_all(trends)
    db_session.flush()

    db_session.add_all([
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        )
        for trend in trends
    ])
    db_session.flush()

    # 5. 인증 사용자를 요청 사이에 전환할 수 있도록 구성
    application = create_app()

    active_user = user_a

    def override_get_db() -> Iterator[Session]:
        yield db_session

    def override_current_user() -> User:
        return active_user

    application.dependency_overrides[
        get_db
    ] = override_get_db

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as client:
            # 6. 사용자 A가 첫 페이지 조회
            first_response = client.get(
                "/api/trends/personalized",
                params={"limit": 1},
            )

            assert first_response.status_code == 200, (
                first_response.text
            )

            first_data = first_response.json()["data"]

            assert len(first_data["items"]) == 1
            assert first_data["has_next"] is True

            user_a_cursor = first_data["next_cursor"]

            assert isinstance(user_a_cursor, str)
            assert user_a_cursor

            # 7. 인증 사용자만 B로 전환
            active_user = user_b

            # 사용자 B가 A의 Cursor를 재사용
            second_response = client.get(
                "/api/trends/personalized",
                params={
                    "limit": 1,
                    "cursor": user_a_cursor,
                },
            )

    finally:
        application.dependency_overrides.clear()

    # 8. 다른 사용자의 Cursor이므로 400
    assert second_response.status_code == 400, (
        second_response.text
    )

    assert second_response.json() == {
        "success": False,
        "statusCode": 400,
        "message": "페이지 정보가 올바르지 않습니다.",
        "data": {
            "reason": "INVALID_CURSOR",
        },
    }


def test_personalized_trends_rejects_cursor_after_interest_change(
    db_session: Session,
) -> None:
    """관심사가 변경되면 기존 Personalized Cursor를 거부한다."""

    # 1. 사용자와 두 Root Category 생성
    user = User(
        name="Personalized Interest Change 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    game_root = Category(
        category_code=CategoryCode.GAME,
        category_name="Personalized Scope Change Game",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    food_root = Category(
        category_code=CategoryCode.FOOD,
        category_name="Personalized Scope Change Food",
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
        category_name="Personalized Scope Change Mobile",
        sort_order=1,
        is_active=True,
        parent_id=game_root.category_id,
    )

    food_child = Category(
        category_code=None,
        category_name="Personalized Scope Change Dessert",
        sort_order=1,
        is_active=True,
        parent_id=food_root.category_id,
    )

    db_session.add_all([
        game_child,
        food_child,
    ])
    db_session.flush()

    # 3. 최초 관심사는 GAME
    user_interest = UserInterestCategory(
        user_id=user.user_id,
        category_id=game_root.category_id,
    )

    db_session.add(user_interest)
    db_session.flush()

    # 4. 첫 페이지 Cursor 발급을 위한 GAME Trend 두 개
    collected_at = datetime(2026, 10, 9, 14, 0, 0)

    game_trends = [
        Trend(
            title=f"Personalized Scope Change Trend {index}",
            normalized_title=(
                f"personalized-scope-change-game-{index}"
            ),
            summary=None,
            thumbnail_url=None,
            status=TrendStatus.ACTIVE,
            first_collected_at=collected_at,
            last_collected_at=collected_at,
            updated_at=None,
        )
        for index in range(2)
    ]

    db_session.add_all(game_trends)
    db_session.flush()

    db_session.add_all([
        TrendCategoryMap(
            trend_id=trend.trend_id,
            category_id=game_child.category_id,
            is_primary=False,
        )
        for trend in game_trends
    ])
    db_session.flush()

    # 5. 실제 MariaDB를 사용하는 API 구성
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
            # 6. GAME 관심사 기준 첫 페이지 조회
            first_response = client.get(
                "/api/trends/personalized",
                params={"limit": 1},
            )

            assert first_response.status_code == 200, (
                first_response.text
            )

            first_data = first_response.json()["data"]

            assert len(first_data["items"]) == 1
            assert first_data["has_next"] is True

            old_cursor = first_data["next_cursor"]

            assert isinstance(old_cursor, str)
            assert old_cursor

            # 7. DB에 저장된 관심사를 GAME → FOOD로 변경
            user_interest.category_id = food_root.category_id
            db_session.flush()

            # 8. 변경 전 Cursor를 그대로 재사용
            stale_response = client.get(
                "/api/trends/personalized",
                params={
                    "limit": 1,
                    "cursor": old_cursor,
                },
            )

            # 9. Cursor 없이 새 관심사 기준 첫 페이지 조회
            fresh_response = client.get(
                "/api/trends/personalized",
                params={"limit": 1},
            )

    finally:
        application.dependency_overrides.clear()

    # 10. 변경 전 Cursor는 INVALID_CURSOR
    assert stale_response.status_code == 400, (
        stale_response.text
    )

    assert stale_response.json() == {
        "success": False,
        "statusCode": 400,
        "message": "페이지 정보가 올바르지 않습니다.",
        "data": {
            "reason": "INVALID_CURSOR",
        },
    }

    # 11. 새로운 관심사 기준 첫 페이지 조회는 정상
    assert fresh_response.status_code == 200, (
        fresh_response.text
    )

    fresh_data = fresh_response.json()["data"]

    # FOOD에 매핑된 Trend가 없으므로 정상적인 빈 목록
    assert fresh_data["items"] == []
    assert fresh_data["has_next"] is False
    assert fresh_data["next_cursor"] is None
