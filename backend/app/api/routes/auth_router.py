from fastapi import APIRouter, status

from app.api.dependencies.auth_dependency import AuthServiceDep, CurrentUserDep
from app.schemas.auth_schema import LoginData, LoginRequest, SessionData
from app.schemas.common_schema import CommonResponse
from app.utils.response import success_response

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/login",
    response_model=CommonResponse[LoginData],
    status_code=status.HTTP_200_OK,
    summary="일반 로그인",
    description=(
        "로그인 ID와 비밀번호를 검증하고 "
        "JWT Access Token과 사용자 정보를 반환합니다."
    ),
)
def login(
    request: LoginRequest,
    service: AuthServiceDep,
) -> CommonResponse[LoginData]:
    """일반 로그인을 처리한다."""
    
    result = service.login(
        login_request=request,
    )
    
    return success_response(
        message="로그인에 성공했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )
    

@router.get(
    "/session",
    response_model=CommonResponse[SessionData],
    status_code=status.HTTP_200_OK,
    summary="현재 인증 세션 조회",
    description=(
        "Bearer Access Token을 검증하고 "
        "현재 사용자의 인증 세션 및 앱 진입 상태를 반환합니다."
    ),
)
def get_session(
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> CommonResponse[SessionData]:
    """현재 인증 사용자의 세션 상태를 반환한다."""
    
    result = service.get_session(
        user=current_user,
    )
    
    return success_response(
        message="인증 세션을 확인했습니다.",
        data=result,
        status_code=status.HTTP_200_OK,
    )