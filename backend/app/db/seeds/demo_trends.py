from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
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
) -> None:
    """전체 트렌드 목록 검증용 Demo 데이터를 생성하거나 검증한다."""

    if app_env.strip().lower() != "local":
        raise DemoTrendSeedError(
            "Demo Trend Seed는 local 환경에서만 실행할 수 있습니다."
        )

    try:
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

        db_session.commit()

    except Exception:
        db_session.rollback()
        raise
