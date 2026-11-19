from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import event, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource


class DemoTrendSeedError(RuntimeError):
    """Demo Trend Seed를 안전하게 실행할 수 없을 때 발생한다."""


_SEED_MODELS = (Category, Trend, TrendCategoryMap, TrendSource)


def _single_seed_bind(db_session: Session) -> Engine | Connection:
    """기본 Session의 모든 Seed ORM 경로가 한 bind를 사용하는지 확인한다."""
    # 사용자 정의 routing Session은 정적 비교만으로 DML 목적지를 증명할 수 없다.
    if (
        not isinstance(db_session, Session)
        or type(db_session).get_bind is not Session.get_bind
        or type(db_session).connection is not Session.connection
    ):
        raise DemoTrendSeedError("Demo Seed guard: session_binding")
    bind = db_session.get_bind()
    if not isinstance(bind, (Engine, Connection)) or any(
        db_session.get_bind(mapper=model) is not bind
        or db_session.get_bind(clause=model.__table__) is not bind
        for model in _SEED_MODELS
    ):
        raise DemoTrendSeedError("Demo Seed guard: session_binding")
    return bind


@contextmanager
def _verified_seed_connection(
    db_session: Session,
    *,
    app_env: str,
    allowed_host: str | None,
    allowed_port: int | None,
    allowed_database: str | None,
    allowed_current_user: str | None,
) -> Iterator[None]:
    """검증 연결과 트랜잭션을 Seed의 마지막 Commit까지 유지한다."""
    listeners = []
    try:
        try:
            if not isinstance(app_env, str) or app_env.strip().lower() != "local":
                raise DemoTrendSeedError(
                    "Demo Trend Seed는 local 환경에서만 실행합니다."
                )
            if (
                any(
                    not isinstance(value, str) or not value.strip()
                    for value in (allowed_host, allowed_database, allowed_current_user)
                )
                or type(allowed_port) is not int
                or not 1 <= allowed_port <= 65535
                or not all(allowed_current_user.rpartition("@")[::2])
            ):
                raise DemoTrendSeedError("Demo Seed guard: approval_settings")
            if db_session.new or db_session.dirty or db_session.deleted:
                raise DemoTrendSeedError("Demo Seed guard: pending_changes")
            bind = _single_seed_bind(db_session)
            engine = bind.engine if isinstance(bind, Connection) else bind
            url = engine.url
            # 현재 지원하는 명시적 TCP URL만 허용한다. 소켓/옵션 파일/다중 host는 거절.
            if (
                url.drivername != "mysql+pymysql"
                or not url.host
                or not re.fullmatch(r"[A-Za-z0-9_.-]+", url.host)
                or url.port is None
                or set(url.query) - {"charset"}
                or url.host != allowed_host
                or url.port != allowed_port
                or url.database != allowed_database
            ):
                raise DemoTrendSeedError("Demo Seed guard: connection_target")

            # Session.connection()은 ORM autoflush를 수행하지 않는다.
            connection = db_session.connection()
            if (
                connection.engine is not engine
                or isinstance(bind, Connection) and connection is not bind
                or any(
                    db_session.connection(bind_arguments={"mapper": model})
                    is not connection
                    for model in _SEED_MODELS
                )
            ):
                raise DemoTrendSeedError("Demo Seed guard: connection_mismatch")
            driver_connection = connection.connection.dbapi_connection
            if driver_connection is None:
                raise DemoTrendSeedError("Demo Seed guard: connection_mismatch")
            transaction = connection.get_transaction()
            nested_transaction = connection.get_nested_transaction()
            session_transaction = db_session.get_transaction()

            def check_connection(*_args, **_kwargs):
                if (
                    connection.closed
                    or connection.invalidated
                    or connection.connection.dbapi_connection is not driver_connection
                    or transaction is None
                    or not transaction.is_active
                    or connection.get_transaction() is not transaction
                    or connection.get_nested_transaction() is not nested_transaction
                    or db_session.get_transaction() is not session_transaction
                    or _single_seed_bind(db_session) is not bind
                ):
                    raise DemoTrendSeedError("Demo Seed guard: connection_changed")

            def reject_new_transaction(*_args, **_kwargs):
                raise DemoTrendSeedError("Demo Seed guard: connection_changed")

            for target, name, listener in (
                (connection, "before_cursor_execute", check_connection),
                (db_session, "before_flush", check_connection),
                (db_session, "before_commit", check_connection),
                (db_session, "after_begin", reject_new_transaction),
            ):
                event.listen(target, name, listener)
                listeners.append((target, name, listener))

            check_connection()
            identity = connection.execute(text(
                "SELECT DATABASE() AS db_name, CURRENT_USER() AS authenticated_user"
            )).mappings().one()
            if (
                identity["db_name"] != allowed_database
                or identity["authenticated_user"] != allowed_current_user
            ):
                raise DemoTrendSeedError("Demo Seed guard: database_identity")
            check_connection()
        except DemoTrendSeedError:
            raise
        except Exception:
            # URL, DBAPI 및 Settings의 입력값을 예외 메시지에 포함하지 않는다.
            raise DemoTrendSeedError("Demo Seed guard: verification_failed") from None
        yield
    finally:
        for target, name, listener in reversed(listeners):
            event.remove(target, name, listener)


@dataclass(frozen=True)
class DemoCategoryRef:
    """Demo Trend가 연결될 세부분류 식별 정보."""

    category_code: CategoryCode
    category_name: str


@dataclass(frozen=True)
class DemoSourceSeed:
    """Demo Trend Source 정의."""

    source_url: str
    source_title: str | None
    platform: TrendSourcePlatform
    collected_at: datetime
    external_id: str | None = None

    @property
    def source_key(self) -> str:
        """URL을 기준으로 안정적인 Demo Source key를 만든다."""

        return sha256(
            self.source_url.encode("utf-8"),
        ).hexdigest()


@dataclass(frozen=True)
class DemoTrendSeed:
    """하나의 Demo Trend 정의."""

    title: str
    normalized_title: str
    summary: str | None
    thumbnail_url: str | None
    status: TrendStatus
    first_collected_at: datetime
    last_collected_at: datetime
    categories: tuple[DemoCategoryRef, ...]
    sources: tuple[DemoSourceSeed, ...]


DEMO_BASE_TIME = datetime(
    2026,
    10,
    1,
    9,
    0,
    0,
)


DEMO_TOPICS: tuple[
    tuple[
        str,
        tuple[DemoCategoryRef, ...],
    ],
    ...,
] = (
    (
        "AI 에이전트 활용 확산",
        (
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "인공지능",
            ),
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "소프트웨어·앱",
            ),
        ),
    ),
    (
        "폴더블 스마트폰 관심 증가",
        (
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "모바일·스마트폰",
            ),
        ),
    ),
    (
        "게이밍 노트북 신제품 화제",
        (
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "PC·하드웨어",
            ),
            DemoCategoryRef(
                CategoryCode.GAME,
                "PC 게임",
            ),
        ),
    ),
    (
        "생산성 앱 활용법 인기",
        (
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "소프트웨어·앱",
            ),
        ),
    ),
    (
        "디지털 플랫폼 구독 서비스 관심",
        (
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "플랫폼·서비스",
            ),
        ),
    ),
    (
        "가을 아우터 스타일 주목",
        (
            DemoCategoryRef(
                CategoryCode.FASHION,
                "의류",
            ),
        ),
    ),
    (
        "러닝화 스타일 인기",
        (
            DemoCategoryRef(
                CategoryCode.FASHION,
                "신발",
            ),
        ),
    ),
    (
        "미니백 코디 관심 증가",
        (
            DemoCategoryRef(
                CategoryCode.FASHION,
                "가방",
            ),
            DemoCategoryRef(
                CategoryCode.FASHION,
                "패션 스타일",
            ),
        ),
    ),
    (
        "액세서리 레이어드 스타일 화제",
        (
            DemoCategoryRef(
                CategoryCode.FASHION,
                "주얼리·액세서리",
            ),
        ),
    ),
    (
        "스트리트 패션 스타일 인기",
        (
            DemoCategoryRef(
                CategoryCode.FASHION,
                "패션 스타일",
            ),
        ),
    ),
    (
        "보습 스킨케어 루틴 관심",
        (
            DemoCategoryRef(
                CategoryCode.BEAUTY,
                "스킨케어",
            ),
        ),
    ),
    (
        "립 메이크업 신제품 화제",
        (
            DemoCategoryRef(
                CategoryCode.BEAUTY,
                "메이크업",
            ),
        ),
    ),
    (
        "헤어 스타일링 팁 인기",
        (
            DemoCategoryRef(
                CategoryCode.BEAUTY,
                "헤어",
            ),
        ),
    ),
    (
        "가을 향수 추천 관심",
        (
            DemoCategoryRef(
                CategoryCode.BEAUTY,
                "향수",
            ),
        ),
    ),
    (
        "셀프 네일 디자인 인기",
        (
            DemoCategoryRef(
                CategoryCode.BEAUTY,
                "네일",
            ),
        ),
    ),
    (
        "모바일 RPG 업데이트 화제",
        (
            DemoCategoryRef(
                CategoryCode.GAME,
                "모바일 게임",
            ),
        ),
    ),
    (
        "PC 인디게임 신작 관심",
        (
            DemoCategoryRef(
                CategoryCode.GAME,
                "PC 게임",
            ),
            DemoCategoryRef(
                CategoryCode.IT_DIGITAL,
                "PC·하드웨어",
            ),
        ),
    ),
    (
        "콘솔 게임 신작 공개",
        (
            DemoCategoryRef(
                CategoryCode.GAME,
                "콘솔 게임",
            ),
        ),
    ),
    (
        "e스포츠 결승전 화제",
        (
            DemoCategoryRef(
                CategoryCode.GAME,
                "e스포츠",
            ),
        ),
    ),
    (
        "게임 구독 서비스 관심",
        (
            DemoCategoryRef(
                CategoryCode.GAME,
                "게임 플랫폼·서비스",
            ),
        ),
    ),
    (
        "신상 디저트 카페 인기",
        (
            DemoCategoryRef(
                CategoryCode.FOOD,
                "카페·디저트",
            ),
        ),
    ),
    (
        "제철 한식 메뉴 관심",
        (
            DemoCategoryRef(
                CategoryCode.FOOD,
                "한식",
            ),
        ),
    ),
    (
        "신작 애니메이션 화제",
        (
            DemoCategoryRef(
                CategoryCode.ENTERTAINMENT,
                "웹툰·애니메이션",
            ),
        ),
    ),
    (
        "음악 페스티벌 관심 증가",
        (
            DemoCategoryRef(
                CategoryCode.ENTERTAINMENT,
                "음악",
            ),
        ),
    ),
    (
        "신작 드라마 공개 화제",
        (
            DemoCategoryRef(
                CategoryCode.ENTERTAINMENT,
                "드라마",
            ),
        ),
    ),
)


def _build_sources(
    number: int,
    last_collected_at: datetime,
) -> tuple[DemoSourceSeed, ...]:
    """테스트 경계를 포함한 결정적인 Source 데이터를 만든다."""

    latest_source = DemoSourceSeed(
        source_url=(
            "https://example.com/"
            f"trend-leader-demo/{number:03d}/latest"
        ),
        source_title=(
            None
            if number == 9
            else f"[DEMO] Trend Source {number:03d}"
        ),
        platform=(
            TrendSourcePlatform.YOUTUBE
            if number % 2 == 0
            else TrendSourcePlatform.GOOGLE
        ),
        collected_at=last_collected_at,
        external_id=f"demo-{number:03d}",
    )

    if number == 1:
        # 같은 collected_at일 때 source_id DESC tie-break를 검증한다.
        same_time_source = DemoSourceSeed(
            source_url=(
                "https://example.com/"
                "trend-leader-demo/001/same-time"
            ),
            source_title="[DEMO] Same Time Source",
            platform=TrendSourcePlatform.SNS,
            collected_at=last_collected_at,
            external_id="demo-001-same-time",
        )

        return (
            latest_source,
            same_time_source,
        )

    if number in {
        8,
        17,
    }:
        older_source = DemoSourceSeed(
            source_url=(
                "https://example.com/"
                f"trend-leader-demo/{number:03d}/older"
            ),
            source_title=(
                f"[DEMO] Older Source {number:03d}"
            ),
            platform=TrendSourcePlatform.ETC,
            collected_at=(
                last_collected_at
                - timedelta(
                    hours=1,
                )
            ),
            external_id=(
                f"demo-{number:03d}-older"
            ),
        )

        return (
            older_source,
            latest_source,
        )

    return (
        latest_source,
    )


def _build_active_demo_trends() -> tuple[DemoTrendSeed, ...]:
    """ACTIVE 25개 Demo Trend 정의를 생성한다."""

    demo_trends: list[DemoTrendSeed] = []

    for number, (
        topic,
        categories,
    ) in enumerate(
        DEMO_TOPICS,
        start=1,
    ):
        # 두 개씩 같은 시각을 사용해 Trend tie-break를 검증한다.
        time_slot = (
            number - 1
        ) // 2

        last_collected_at = (
            DEMO_BASE_TIME
            - timedelta(
                minutes=time_slot * 10,
            )
        )

        seed = DemoTrendSeed(
            title=f"[DEMO] {topic}",
            normalized_title=(
                f"demo-trend-list-{number:03d}"
            ),
            summary=(
                None
                if number in {
                    5,
                    13,
                }
                else (
                    "Trend Leader 전체 목록 화면 검증을 위한 "
                    f"Demo Trend {number:03d}입니다."
                )
            ),
            thumbnail_url=(
                None
                if number in {
                    7,
                    18,
                }
                else (
                    "https://picsum.photos/"
                    f"seed/trend-leader-{number:03d}/800/450"
                )
            ),
            status=TrendStatus.ACTIVE,
            first_collected_at=(
                last_collected_at
                - timedelta(
                    days=1,
                )
            ),
            last_collected_at=last_collected_at,
            categories=categories,
            sources=_build_sources(
                number,
                last_collected_at,
            ),
        )

        demo_trends.append(
            seed,
        )

    return tuple(
        demo_trends,
    )


ACTIVE_DEMO_TRENDS = _build_active_demo_trends()


HIDDEN_DEMO_TREND = DemoTrendSeed(
    title="[DEMO] 숨김 검증용 트렌드",
    normalized_title="demo-trend-list-hidden-001",
    summary="HIDDEN Trend가 전체 목록에서 제외되는지 확인합니다.",
    thumbnail_url=None,
    status=TrendStatus.HIDDEN,
    first_collected_at=(
        DEMO_BASE_TIME
        - timedelta(
            days=1,
        )
    ),
    last_collected_at=(
        DEMO_BASE_TIME
        + timedelta(
            hours=1,
        )
    ),
    categories=(
        DemoCategoryRef(
            CategoryCode.IT_DIGITAL,
            "플랫폼·서비스",
        ),
    ),
    sources=(
        DemoSourceSeed(
            source_url=(
                "https://example.com/"
                "trend-leader-demo/hidden-001"
            ),
            source_title="[DEMO] Hidden Source",
            platform=TrendSourcePlatform.ETC,
            collected_at=(
                DEMO_BASE_TIME
                + timedelta(
                    hours=1,
                )
            ),
            external_id="demo-hidden-001",
        ),
    ),
)


DEMO_TRENDS: tuple[DemoTrendSeed, ...] = (
    *ACTIVE_DEMO_TRENDS,
    HIDDEN_DEMO_TREND,
)


def _resolve_category(
    db_session: Session,
    category_ref: DemoCategoryRef,
) -> Category:
    """Master Category를 코드와 부모 맥락의 이름으로 식별한다."""

    root_statement = select(
        Category,
    ).where(
        Category.category_code
        == category_ref.category_code,
    )

    root = db_session.scalars(
        root_statement,
    ).one_or_none()

    identifier = (
        f"{category_ref.category_code.value} / "
        f"{category_ref.category_name}"
    )

    if (
        root is None
        or root.parent_id is not None
        or not root.is_active
    ):
        raise DemoTrendSeedError(
            f"{identifier}: 활성 대분류를 찾을 수 없습니다."
        )

    child_statement = select(
        Category,
    ).where(
        Category.parent_id
        == root.category_id,
        Category.category_name
        == category_ref.category_name,
    )

    children = list(
        db_session.scalars(
            child_statement,
        ).all()
    )

    if len(children) != 1:
        raise DemoTrendSeedError(
            f"{identifier}: 세부분류를 하나로 식별할 수 없습니다."
        )

    child = children[0]

    if (
        child.category_code is not None
        or not child.is_active
    ):
        raise DemoTrendSeedError(
            f"{identifier}: 사용할 수 없는 세부분류입니다."
        )

    return child


def _verify_existing_trend(
    db_session: Session,
    *,
    trend: Trend,
    seed: DemoTrendSeed,
    category_ids: tuple[int, ...],
) -> None:
    """기존 Demo Row가 현재 Seed 정의와 정확히 일치하는지 검증한다."""

    expected_fields = {
        "title": seed.title,
        "summary": seed.summary,
        "thumbnail_url": seed.thumbnail_url,
        "status": seed.status,
        "first_collected_at": seed.first_collected_at,
        "last_collected_at": seed.last_collected_at,
    }

    mismatched_fields = [
        field_name
        for field_name, expected_value
        in expected_fields.items()
        if getattr(
            trend,
            field_name,
        )
        != expected_value
    ]

    if mismatched_fields:
        fields = ", ".join(
            mismatched_fields,
        )

        raise DemoTrendSeedError(
            f"{seed.normalized_title}: "
            f"기존 Demo Trend 정의 불일치 ({fields})"
        )

    existing_category_ids = tuple(
        sorted(
            db_session.scalars(
                select(
                    TrendCategoryMap.category_id,
                ).where(
                    TrendCategoryMap.trend_id
                    == trend.trend_id,
                )
            ).all()
        )
    )

    if existing_category_ids != tuple(
        sorted(
            category_ids,
        )
    ):
        raise DemoTrendSeedError(
            f"{seed.normalized_title}: "
            "기존 Demo Category Mapping 불일치"
        )

    existing_sources = list(
        db_session.scalars(
            select(
                TrendSource,
            ).where(
                TrendSource.trend_id
                == trend.trend_id,
            )
        ).all()
    )

    source_by_key = {
        source.source_key: source
        for source in existing_sources
    }

    if set(
        source_by_key,
    ) != {
        source_seed.source_key
        for source_seed in seed.sources
    }:
        raise DemoTrendSeedError(
            f"{seed.normalized_title}: "
            "기존 Demo Source 구성 불일치"
        )

    for source_seed in seed.sources:
        source = source_by_key[
            source_seed.source_key
        ]

        if (
            source.source_url
            != source_seed.source_url
            or source.source_title
            != source_seed.source_title
            or source.platform
            != source_seed.platform
            or source.collected_at
            != source_seed.collected_at
            or source.external_id
            != source_seed.external_id
        ):
            raise DemoTrendSeedError(
                f"{seed.normalized_title}: "
                "기존 Demo Source 정의 불일치"
            )


def _create_demo_trend(
    db_session: Session,
    *,
    seed: DemoTrendSeed,
    category_ids: tuple[int, ...],
) -> None:
    """새 Demo Trend와 연관 데이터를 생성한다."""

    trend = Trend(
        title=seed.title,
        normalized_title=seed.normalized_title,
        summary=seed.summary,
        thumbnail_url=seed.thumbnail_url,
        status=seed.status,
        first_collected_at=seed.first_collected_at,
        last_collected_at=seed.last_collected_at,
        updated_at=None,
    )

    db_session.add(
        trend,
    )
    db_session.flush()

    for category_id in category_ids:
        db_session.add(
            TrendCategoryMap(
                trend_id=trend.trend_id,
                category_id=category_id,
                is_primary=False,
            )
        )

    for source_seed in seed.sources:
        db_session.add(
            TrendSource(
                source_key=source_seed.source_key,
                source_url=source_seed.source_url,
                source_title=source_seed.source_title,
                platform=source_seed.platform,
                collected_at=source_seed.collected_at,
                external_id=source_seed.external_id,
                trend_id=trend.trend_id,
            )
        )


def seed_demo_trends(
    db_session: Session,
    *,
    app_env: str,
    allowed_host: str | None = None,
    allowed_port: int | None = None,
    allowed_database: str | None = None,
    allowed_current_user: str | None = None,
) -> None:
    """전체 트렌드 목록 검증용 Demo 데이터를 생성하거나 검증한다."""

    try:
        with _verified_seed_connection(
            db_session,
            app_env=app_env,
            allowed_host=allowed_host,
            allowed_port=allowed_port,
            allowed_database=allowed_database,
            allowed_current_user=allowed_current_user,
        ):
            _seed_demo_rows(db_session)
            db_session.commit()

    except Exception:
        db_session.rollback()
        raise


def _seed_demo_rows(db_session: Session) -> None:
    """검증된 Session에서 기존 Demo 데이터 계약을 적용한다."""
    for seed in DEMO_TRENDS:
        category_ids = tuple(
            _resolve_category(
                db_session,
                category_ref,
            ).category_id
            for category_ref in seed.categories
        )

        existing = db_session.scalars(
            select(
                Trend,
            ).where(
                Trend.normalized_title
                == seed.normalized_title,
            )
        ).one_or_none()

        if existing is not None:
            _verify_existing_trend(
                db_session,
                trend=existing,
                seed=seed,
                category_ids=category_ids,
            )
            continue

        _create_demo_trend(
            db_session,
            seed=seed,
            category_ids=category_ids,
        )
