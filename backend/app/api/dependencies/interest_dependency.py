from typing import Annotated

from fastapi import Depends

from app.api.dependencies.category_dependency import CategoryRepositoryDep
from app.api.dependencies.db_dependency import DbSessionDep
from app.repositories.interest_repository import InterestRepository
from app.services.interest_service import InterestService


def get_interest_repository(
    db: DbSessionDep,
) -> InterestRepository:
    """요청 단위 InterestRepository를 생성한다."""

    return InterestRepository(
        db=db,
    )


InterestRepositoryDep = Annotated[
    InterestRepository,
    Depends(get_interest_repository),
]


def get_interest_service(
    db: DbSessionDep,
    category_repository: CategoryRepositoryDep,
    interest_repository: InterestRepositoryDep,
) -> InterestService:
    """관심사 저장에 필요한 Repository를 조립해 InterestService를 생성한다."""

    return InterestService(
        db=db,
        category_repository=category_repository,
        interest_repository=interest_repository,
    )


InterestServiceDep = Annotated[
    InterestService,
    Depends(get_interest_service),
]