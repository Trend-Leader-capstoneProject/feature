from typing import Annotated

from fastapi import (
    APIRouter,
    Query,
    status,
)

from app.api.dependencies.auth_dependency import (
    CurrentUserDep,
)
from app.api.dependencies.trend_dependency import (
    PersonalizedTrendServiceDep,
    TrendServiceDep,
)
from app.schemas.common_schema import CommonResponse
from app.schemas.error_schema import ErrorResponse
from app.schemas.trend_schema import TrendListData
from app.utils.response import success_response

router = APIRouter(
    prefix="/trends",
    tags=["trends"],
)


@router.get(
    "",
    response_model=CommonResponse[TrendListData],
    status_code=status.HTTP_200_OK,
    summary="전체 트렌드 목록 조회",
    description=(
        "인증 없이 ACTIVE 트렌드를 최신 수집 순으로 조회합니다. "
        "Category 필터와 Cursor 기반 페이지네이션을 지원합니다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "잘못된 Cursor 또는 사용할 수 없는 Category"
            ),
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "존재하지 않는 Category",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Query Parameter 검증 실패",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "서버 오류",
        },
    },
)
def list_trends(
    service: TrendServiceDep,
    cursor: Annotated[
        str | None,
        Query(
            description="서버가 발급한 다음 페이지 Cursor",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="페이지당 Trend 개수",
        ),
    ] = 20,
    category_id: Annotated[
        int | None,
        Query(
            ge=1,
            description="필터할 대분류 또는 세부분류 ID",
        ),
    ] = None,
) -> CommonResponse[TrendListData]:
    """전체 최신 Trend 목록을 조회한다."""

    result = service.list_trends(
        category_id=category_id,
        limit=limit,
        cursor=cursor,
    )

    return success_response(
        message="전체 트렌드를 조회했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/personalized",
    response_model=CommonResponse[TrendListData],
    status_code=status.HTTP_200_OK,
    summary="관심사 기반 맞춤 트렌드 목록 조회",
    description=(
        "인증된 사용자의 활성 관심사를 기준으로 "
        "ACTIVE 트렌드를 최신순으로 조회합니다. "
        "Cursor 기반 페이지네이션을 지원합니다."
    ),
)
def list_personalized_trends(
    current_user: CurrentUserDep,
    service: PersonalizedTrendServiceDep,
    cursor: Annotated[
        str | None,
        Query(
            description="서버가 발급한 Personalized Cursor",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="페이지당 Trend 개수",
        ),
    ] = 20,
) -> CommonResponse[TrendListData]:
    """현재 사용자의 관심사 기반 Trend 목록을 조회한다."""

    result = service.list_personalized_trends(
        user_id=current_user.user_id,
        limit=limit,
        cursor=cursor,
    )

    return success_response(
        message="맞춤 트렌드를 조회했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )
