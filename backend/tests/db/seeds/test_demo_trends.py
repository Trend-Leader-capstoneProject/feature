from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.seeds.category_master import (
    seed_category_master,
)
from app.db.seeds.demo_trends import (
    DemoTrendSeedError,
    seed_demo_trends,
)
from app.models.db_enums import TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource

pytestmark = pytest.mark.integration


def test_seed_demo_trends_rejects_non_local_environment(
    db_session: Session,
) -> None:
    """Demo Seed는 local 환경 외에서는 실행하지 않는다."""

    with pytest.raises(
        DemoTrendSeedError,
        match="local",
    ):
        seed_demo_trends(
            db_session,
            app_env="production",
        )


def test_seed_demo_trends_requires_category_master(
    db_session: Session,
) -> None:
    """Category Master가 없으면 임의 Category를 만들지 않고 실패한다."""

    with pytest.raises(
        DemoTrendSeedError,
    ):
        seed_demo_trends(
            db_session,
            app_env="local",
        )

    trend_count = db_session.execute(
        select(
            func.count(),
        ).select_from(
            Trend,
        )
    ).scalar_one()

    assert trend_count == 0


def test_seed_demo_trends_creates_expected_demo_dataset(
    db_session: Session,
) -> None:
    """ACTIVE 25개와 별도 HIDDEN Demo Trend를 생성한다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    active_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            Trend,
        )
        .where(
            Trend.normalized_title.like(
                "demo-trend-list-%"
            ),
            Trend.status
            == TrendStatus.ACTIVE,
        )
    ).scalar_one()

    hidden_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            Trend,
        )
        .where(
            Trend.normalized_title.like(
                "demo-trend-list-%"
            ),
            Trend.status
            == TrendStatus.HIDDEN,
        )
    ).scalar_one()

    source_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            TrendSource,
        )
        .join(
            Trend,
            Trend.trend_id
            == TrendSource.trend_id,
        )
        .where(
            Trend.normalized_title.like(
                "demo-trend-list-%"
            )
        )
    ).scalar_one()

    assert active_count == 25
    assert hidden_count >= 1

    # 정상 Demo Trend는 모두 Source를 가져야 한다.
    assert source_count >= 26


def test_seed_demo_trends_is_idempotent(
    db_session: Session,
) -> None:
    """같은 Demo Seed를 재실행해도 Trend가 중복되지 않는다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    first_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            Trend,
        )
        .where(
            Trend.normalized_title.like(
                "demo-trend-list-%"
            )
        )
    ).scalar_one()

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    second_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            Trend,
        )
        .where(
            Trend.normalized_title.like(
                "demo-trend-list-%"
            )
        )
    ).scalar_one()

    assert first_count == 26
    assert second_count == first_count


def test_seed_demo_trends_preserves_non_demo_trends(
    db_session: Session,
) -> None:
    """Demo Seed 실행은 기존 비-Demo Trend를 수정하거나 삭제하지 않는다."""

    seed_category_master(
        db_session,
    )

    existing = Trend(
        title="기존 개발 트렌드",
        normalized_title=(
            "existing-development-trend"
        ),
        summary="보존되어야 하는 데이터",
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
    )

    db_session.add(
        existing,
    )
    db_session.flush()

    existing_id = existing.trend_id

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    preserved = db_session.get(
        Trend,
        existing_id,
    )

    assert preserved is not None
    assert (
        preserved.normalized_title
        == "existing-development-trend"
    )
    assert (
        preserved.summary
        == "보존되어야 하는 데이터"
    )

def test_demo_seed_contains_required_boundary_cases(
    db_session: Session,
) -> None:
    """Demo 데이터가 화면·정렬 검증에 필요한 경계 사례를 포함한다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    demo_trends = list(
        db_session.scalars(
            select(
                Trend,
            )
            .where(
                Trend.normalized_title.like(
                    "demo-trend-list-%"
                ),
                Trend.status
                == TrendStatus.ACTIVE,
            )
            .order_by(
                Trend.normalized_title.asc(),
            )
        ).all()
    )

    assert len(
        demo_trends,
    ) == 25

    assert any(
        trend.summary is None
        for trend in demo_trends
    )

    assert any(
        trend.thumbnail_url is None
        for trend in demo_trends
    )

    # DB 저장 계약은 UTC 기준 naive datetime이다.
    assert all(
        trend.last_collected_at.tzinfo is None
        for trend in demo_trends
    )

    # Trend 정렬 tie-break 검증을 위한 동일 시각 데이터가 존재한다.
    collected_times = [
        trend.last_collected_at
        for trend in demo_trends
    ]

    assert len(
        collected_times,
    ) > len(
        set(
            collected_times,
        )
    )

    nullable_source_title_count = (
        db_session.execute(
            select(
                func.count(),
            )
            .select_from(
                TrendSource,
            )
            .join(
                Trend,
                Trend.trend_id
                == TrendSource.trend_id,
            )
            .where(
                Trend.normalized_title.like(
                    "demo-trend-list-%"
                ),
                TrendSource.source_title.is_(
                    None,
                ),
            )
        ).scalar_one()
    )

    assert nullable_source_title_count >= 1

def test_demo_seed_contains_multiple_categories_and_sources(
    db_session: Session,
) -> None:
    """일부 Demo Trend는 복수 Category와 복수 Source를 가진다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    category_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            TrendCategoryMap,
        )
        .join(
            Trend,
            Trend.trend_id
            == TrendCategoryMap.trend_id,
        )
        .where(
            Trend.normalized_title
            == "demo-trend-list-001",
        )
    ).scalar_one()

    source_count = db_session.execute(
        select(
            func.count(),
        )
        .select_from(
            TrendSource,
        )
        .join(
            Trend,
            Trend.trend_id
            == TrendSource.trend_id,
        )
        .where(
            Trend.normalized_title
            == "demo-trend-list-001",
        )
    ).scalar_one()

    assert category_count == 2
    assert source_count == 2

def test_demo_seed_supports_latest_source_tie_break(
    db_session: Session,
) -> None:
    """같은 수집 시각에서는 더 큰 source_id가 최신 Source가 된다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
    )

    trend = db_session.scalars(
        select(
            Trend,
        ).where(
            Trend.normalized_title
            == "demo-trend-list-001",
        )
    ).one()

    sources = list(
        db_session.scalars(
            select(
                TrendSource,
            )
            .where(
                TrendSource.trend_id
                == trend.trend_id,
            )
            .order_by(
                TrendSource.collected_at.desc(),
                TrendSource.source_id.desc(),
            )
        ).all()
    )

    assert len(
        sources,
    ) == 2

    assert (
        sources[0].collected_at
        == sources[1].collected_at
    )

    assert (
        sources[0].source_id
        > sources[1].source_id
    )

    assert (
        sources[0].source_title
        == "[DEMO] Same Time Source"
    )
