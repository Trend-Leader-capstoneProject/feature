from fastapi import APIRouter, status

from app.api.dependencies.auth_dependency import CurrentUserDep
from app.api.dependencies.interest_dependency import InterestServiceDep
from app.schemas.common_schema import CommonResponse
from app.schemas.error_schema import ErrorResponse
from app.schemas.interest_schema import (
    InterestCreateData,
    InterestCreateRequest,
    InterestReadData,
    InterestUpdateData,
    InterestUpdateRequest,
)
from app.utils.response import success_response

router = APIRouter(
    prefix="/users/me/interests",
    tags=["interests"],
)


@router.post(
    "",
    response_model=CommonResponse[InterestCreateData],
    status_code=status.HTTP_201_CREATED,
    summary="최초 관심사 저장",
    description=(
        "인증된 사용자가 회원가입 후 선택한 "
        "활성 대분류 카테고리를 최초 관심사로 저장합니다."
    ),
)
def create_interests(
    request: InterestCreateRequest,
    current_user: CurrentUserDep,
    service: InterestServiceDep,
) -> CommonResponse[InterestCreateData]:
    """현재 사용자의 최초 관심사를 저장한다."""

    result = service.create_interests(
        user_id=current_user.user_id,
        category_ids=request.category_ids,
    )

    return success_response(
        message="관심사를 저장했습니다.",
        data=result,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=CommonResponse[InterestReadData],
    status_code=status.HTTP_200_OK,
    summary="현재 관심사 조회",
    description=(
        "인증된 사용자의 현재 관심사 카테고리 ID 집합을 조회합니다. "
        "저장된 관심사가 없으면 빈 배열을 반환합니다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "인증 실패",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "서버 오류",
        },
    },
)
def get_interests(
    current_user: CurrentUserDep,
    service: InterestServiceDep,
) -> CommonResponse[InterestReadData]:
    """현재 사용자의 저장된 관심사를 조회한다."""

    result = service.get_interests(
        user_id=current_user.user_id,
    )

    return success_response(
        message="관심사를 조회했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )


@router.put(
    "",
    response_model=CommonResponse[InterestUpdateData],
    status_code=status.HTTP_200_OK,
    summary="관심사 수정",
    description=(
        "인증된 사용자의 기존 관심사 전체 집합을 "
        "요청된 활성 대분류 카테고리 집합으로 교체합니다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "비활성 또는 하위 카테고리 포함",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "인증 실패",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "존재하지 않는 카테고리 포함",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "수정할 기존 관심사가 없는 상태 충돌",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "요청 데이터 검증 실패",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "서버 오류",
        },
    },
)
def update_interests(
    request: InterestUpdateRequest,
    current_user: CurrentUserDep,
    service: InterestServiceDep,
) -> CommonResponse[InterestUpdateData]:
    """현재 사용자의 기존 관심사 전체 집합을 수정한다."""

    result = service.update_interests(
        user_id=current_user.user_id,
        category_ids=request.category_ids,
    )

    return success_response(
        message="관심사를 수정했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )
