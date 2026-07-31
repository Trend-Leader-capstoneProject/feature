from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.category_repository import CategoryRepository
from app.services.category_service import CategoryService

DbSessionDep = Annotated[
    Session,
    Depends(get_db),
]


def get_category_repository(
    db: DbSessionDep,
) -> CategoryRepository:
    """요청 단위 CategoryRepository를 생성한다."""

    return CategoryRepository(db=db)


CategoryRepositoryDep = Annotated[
    CategoryRepository,
    Depends(get_category_repository),
]


def get_category_service(
    category_repository: CategoryRepositoryDep,
) -> CategoryService:
    """CategoryRepository가 주입된 CategoryService를 생성한다."""

    return CategoryService(
        category_repository=category_repository,
    )


CategoryServiceDep = Annotated[
    CategoryService,
    Depends(get_category_service),
]
