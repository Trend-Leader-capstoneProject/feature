from typing import Any

from fastapi import APIRouter, status

from app.api.dependencies.category_dependency import CategoryServiceDep
from app.schemas.category_schema import CategoryListData
from app.schemas.common_schema import CommonResponse
from app.utils.response import success_response

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get(
    "",
    response_model=CommonResponse[CategoryListData],
    status_code=status.HTTP_200_OK,
    summary="카테고리 목록 조회",
    description=(
        "활성 상태인 대분류와 세부분류 카테고리를 "
        "화면 노출 순서에 따라 계층 구조로 조회합니다."
    ),
)
def list_categories(
    service: CategoryServiceDep,
) -> dict[str, Any]:
    """관심사 선택 화면에서 사용하는 카테고리 목록을 조회한다."""

    result = service.list_categories()

    return success_response(
        message="카테고리 목록을 조회했습니다.",
        data=result.model_dump(),
        status_code=status.HTTP_200_OK,
    )