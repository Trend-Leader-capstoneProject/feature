from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.seeds import demo_trends as seed_module
from app.db.seeds.category_master import (
    seed_category_master,
)
from app.db.seeds.demo_trends import (
    DemoTrendSeedError,
    seed_demo_trends,
)
from app.models.category import Category
from app.models.db_enums import TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource

pytestmark = pytest.mark.integration


def test_seed_demo_trends_rejects_non_local_environment(
    db_session: Session,
    demo_seed_approval: dict[str, object],
) -> None:
    """Demo Seed는 local 환경 외에서는 실행하지 않는다."""

    with pytest.raises(
        DemoTrendSeedError,
        match="local",
    ):
        seed_demo_trends(
            db_session,
            app_env="production",
            **demo_seed_approval,
        )


def test_seed_demo_trends_requires_category_master(
    db_session: Session,
    demo_seed_approval: dict[str, object],
) -> None:
    """Category Master가 없으면 임의 Category를 만들지 않고 실패한다."""

    with pytest.raises(
        DemoTrendSeedError,
        match="활성 대분류",
    ):
        seed_demo_trends(
            db_session,
            app_env="local",
            **demo_seed_approval,
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
    demo_seed_approval: dict[str, object],
) -> None:
    """ACTIVE 25개와 별도 HIDDEN Demo Trend를 생성한다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
        **demo_seed_approval,
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
    assert hidden_count == 1

    # 정상 Demo Trend는 모두 Source를 가져야 한다.
    assert source_count == 29


def test_seed_demo_trends_is_idempotent(
    db_session: Session,
    demo_seed_approval: dict[str, object],
) -> None:
    """같은 Demo Seed를 재실행해도 Trend가 중복되지 않는다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
        **demo_seed_approval,
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
        **demo_seed_approval,
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
    demo_seed_approval: dict[str, object],
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
        **demo_seed_approval,
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
    demo_seed_approval: dict[str, object],
) -> None:
    """Demo 데이터가 화면·정렬 검증에 필요한 경계 사례를 포함한다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
        **demo_seed_approval,
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
    demo_seed_approval: dict[str, object],
) -> None:
    """일부 Demo Trend는 복수 Category와 복수 Source를 가진다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
        **demo_seed_approval,
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
    demo_seed_approval: dict[str, object],
) -> None:
    """같은 수집 시각에서는 더 큰 source_id가 최신 Source가 된다."""

    seed_category_master(
        db_session,
    )

    seed_demo_trends(
        db_session,
        app_env="local",
        **demo_seed_approval,
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


def test_seed_insert_failure_rolls_back_and_preserves_baseline(
    db_session: Session,
    demo_seed_approval: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """실제 첫 INSERT를 관측한 뒤 실패시키고 해당 Seed 전체만 되돌린다."""
    seed_category_master(db_session)
    baseline = Trend(
        title="기존 원본", normalized_title="existing-rollback-baseline",
        summary="보존", status=TrendStatus.ACTIVE,
    )
    db_session.add(baseline)
    db_session.commit()  # Fixture의 외부 Transaction 내부에 기준 데이터를 고정한다.
    baseline_id = baseline.trend_id
    connection = db_session.connection()
    inserts = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            inserts.append(statement)

    original = seed_module._create_demo_trend
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected seed failure")
        original(*args, **kwargs)

    monkeypatch.setattr(seed_module, "_create_demo_trend", fail_second)
    event.listen(connection, "before_cursor_execute", observe)
    try:
        with pytest.raises(RuntimeError, match="injected seed failure"):
            seed_demo_trends(db_session, app_env="local", **demo_seed_approval)
    finally:
        event.remove(connection, "before_cursor_execute", observe)

    assert inserts
    assert db_session.scalar(select(func.count()).select_from(Trend)) == 1
    preserved = db_session.get(Trend, baseline_id)
    assert preserved.title == "기존 원본"
    assert preserved.summary == "보존"


def test_seed_flush_integrity_error_preserves_baseline_and_outer_transaction(
    db_session: Session,
    demo_seed_approval: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MariaDB UNIQUE 위반으로 실패한 flush까지 Seed Savepoint에서 되돌린다."""
    connection = db_session.get_bind()
    outer_transaction = connection.get_transaction()
    models = (Category, Trend, TrendCategoryMap, TrendSource)

    def counts():
        return tuple(
            connection.scalar(select(func.count()).select_from(model))
            for model in models
        )

    initial_counts = counts()
    # Master/기준 데이터의 commit도 이 Savepoint 안에만 남긴다.
    cleanup_savepoint = connection.begin_nested()
    original_rollback = db_session.rollback
    successful_inserts = []
    failed_session_states = []

    def observe_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            successful_inserts.append(statement)

    def rollback():
        failed_session_states.append(not db_session.is_active)
        original_rollback()

    listener_attached = False
    try:
        seed_category_master(db_session)
        baseline = Trend(
            title="Flush 실패 전 기준 데이터",
            normalized_title="existing-flush-error-baseline",
            summary="보존", status=TrendStatus.ACTIVE,
        )
        db_session.add(baseline)
        db_session.commit()
        baseline_id = baseline.trend_id
        baseline_query = select(Trend.__table__).where(Trend.trend_id == baseline_id)
        category_query = select(Category.__table__).order_by(Category.category_id)
        baseline_before = connection.execute(baseline_query).one()
        categories_before = connection.execute(category_query).all()
        counts_before = counts()
        original_create = seed_module._create_demo_trend
        calls = 0

        def duplicate_second(session, *, seed, category_ids):
            nonlocal calls
            calls += 1
            if calls == 2:
                # ORM과 초기 Migration의 uq_trends_normalized_title을 실제 위반한다.
                seed = replace(seed, normalized_title=baseline.normalized_title)
            original_create(session, seed=seed, category_ids=category_ids)

        monkeypatch.setattr(seed_module, "_create_demo_trend", duplicate_second)
        monkeypatch.setattr(db_session, "rollback", rollback)
        event.listen(connection, "after_cursor_execute", observe_insert)
        listener_attached = True

        with pytest.raises(IntegrityError) as error:
            seed_demo_trends(db_session, app_env="local", **demo_seed_approval)

        assert error.value.orig.args[0] == 1062  # MariaDB duplicate entry
        assert calls == 2
        assert any("INSERT INTO trends" in sql for sql in successful_inserts)
        assert failed_session_states == [True]  # 실제 failed-flush Session 상태
        assert db_session.is_active
        assert not db_session.in_transaction()
        assert cleanup_savepoint.is_active
        assert connection.get_transaction() is outer_transaction
        assert outer_transaction.is_active
        assert counts() == counts_before
        assert connection.execute(baseline_query).one() == baseline_before
        assert connection.execute(category_query).all() == categories_before
        assert connection.scalar(select(func.count()).select_from(Trend).where(
            Trend.normalized_title == seed_module.DEMO_TRENDS[0].normalized_title,
        )) == 0
    finally:
        if listener_attached:
            event.remove(connection, "after_cursor_execute", observe_insert)
        original_rollback()
        cleanup_savepoint.rollback()

    assert counts() == initial_counts
    assert connection.get_transaction() is outer_transaction
    assert outer_transaction.is_active


@pytest.mark.parametrize("drift", ["trend", "source", "mapping"])
def test_seed_drift_rolls_back_partial_rows_and_preserves_existing_data(
    db_session: Session,
    demo_seed_approval: dict[str, object],
    drift: str,
) -> None:
    """늦은 Demo drift를 발견하면 앞서 재생성한 Demo도 Rollback한다."""
    seed_category_master(db_session)
    baseline = Trend(
        title="기존 비 Demo", normalized_title="existing-drift-baseline",
        summary="보존", status=TrendStatus.ACTIVE,
    )
    db_session.add(baseline)
    db_session.commit()
    baseline_id = baseline.trend_id
    seed_demo_trends(db_session, app_env="local", **demo_seed_approval)

    first = db_session.scalars(select(Trend).where(
        Trend.normalized_title == "demo-trend-list-001",
    )).one()
    later = db_session.scalars(select(Trend).where(
        Trend.normalized_title == "demo-trend-list-025",
    )).one()
    db_session.delete(first)  # 다음 실행의 앞부분에서 INSERT가 일어나게 한다.
    if drift == "trend":
        later.summary = "drift"
    elif drift == "source":
        source = db_session.scalars(select(TrendSource).where(
            TrendSource.trend_id == later.trend_id,
        )).first()
        source.source_title = "drift"
    else:
        mapping = db_session.scalars(select(TrendCategoryMap).where(
            TrendCategoryMap.trend_id == later.trend_id,
        )).first()
        db_session.delete(mapping)
    db_session.commit()
    before = db_session.scalar(select(func.count()).select_from(Trend))

    with pytest.raises(DemoTrendSeedError):
        seed_demo_trends(db_session, app_env="local", **demo_seed_approval)

    assert db_session.scalar(select(func.count()).select_from(Trend)) == before
    assert db_session.scalar(select(Trend).where(
        Trend.normalized_title == "demo-trend-list-001",
    )) is None
    assert db_session.get(Trend, baseline_id).summary == "보존"


def test_seed_identity_and_dml_use_fixture_connection_and_keep_outer_transaction(
    db_session: Session,
    demo_seed_approval: dict[str, object],
) -> None:
    seed_category_master(db_session)
    connection = db_session.get_bind()
    outer = connection.get_transaction()
    isolated_savepoint = connection.begin_nested()
    observed = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if "DATABASE()" in statement or statement.lstrip().upper().startswith("INSERT"):
            observed.append((conn, statement))

    event.listen(connection, "before_cursor_execute", observe)
    try:
        with Session(
            bind=connection, autoflush=False,
            join_transaction_mode="create_savepoint",
        ) as isolated_session:
            seed_demo_trends(isolated_session, app_env="local", **demo_seed_approval)
        assert isolated_savepoint.is_active
    finally:
        event.remove(connection, "before_cursor_execute", observe)
        isolated_savepoint.rollback()
    assert any("DATABASE()" in statement for _, statement in observed)
    assert any(
        statement.lstrip().upper().startswith("INSERT") for _, statement in observed
    )
    assert all(conn is connection for conn, _ in observed)
    assert connection.get_transaction() is outer
    assert outer.is_active
    assert db_session.scalar(select(func.count()).select_from(Trend)) == 0
