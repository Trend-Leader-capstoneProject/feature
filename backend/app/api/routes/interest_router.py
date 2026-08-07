from fastapi import APIRouter, status

from app.api.dependencies.auth_dependency import CurrentUserDep
from app.api.dependencies.interest_dependency import InterestServiceDep
from app.schemas.common_schema import CommonResponse
from app.schemas.interest_schema import (
    InterestCreateData,
    InterestCreateRequest,
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