from typing import Annotated

from fastapi import Depends

from app.api.dependencies.category_dependency import (
    CategoryRepositoryDep,
)
from app.api.dependencies.db_dependency import DbSessionDep
from app.repositories.trend_repository import TrendRepository
from app.services.trend_service import TrendService


def get_trend_repository(
    db: DbSessionDep,
) -> TrendRepository:
    """요청 단위 TrendRepository를 생성한다."""

    return TrendRepository(
        db=db,
    )


TrendRepositoryDep = Annotated[
    TrendRepository,
    Depends(get_trend_repository),
]


def get_trend_service(
    category_repository: CategoryRepositoryDep,
    trend_repository: TrendRepositoryDep,
) -> TrendService:
    """Trend 목록 조회에 필요한 의존성을 조립한다."""

    return TrendService(
        category_repository=category_repository,
        trend_repository=trend_repository,
    )


TrendServiceDep = Annotated[
    TrendService,
    Depends(get_trend_service),
]
