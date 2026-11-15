from typing import Annotated

from fastapi import Depends

from app.api.dependencies.db_dependency import DbSessionDep
from app.services.account_service import AccountService


def get_account_service(db: DbSessionDep) -> AccountService:
    return AccountService(db)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
