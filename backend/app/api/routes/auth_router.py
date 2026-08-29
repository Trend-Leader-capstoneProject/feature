from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies.auth_dependency import AuthServiceDep, CurrentUserDep
from app.schemas.auth_schema import (
    LOGIN_ID_PATTERN,
    CheckLoginIdData,
    LoginData,
    LoginRequest,
    SessionData,
    SignupData,
    SignupRequest,
)
from app.schemas.common_schema import CommonResponse
from app.utils.response import success_response

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/signup",
    response_model=CommonResponse[SignupData],
    status_code=status.HTTP_201_CREATED,
    summary="일반 회원가입",
    description=(
        "일반 회원가입 사용자를 생성하고 "
        "JWT Access Token과 초기 인증 세션 정보를 반환합니다."
    ),
)
def signup(
    request: SignupRequest,
    service: AuthServiceDep,
) -> CommonResponse[SignupData]:
    """일반 회원가입을 처리한다."""

    result = service.signup(
        signup_request=request,
    )

    return success_response(
        message="회원가입이 완료되었습니다.",
        data=result,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/check-login-id",
    response_model=CommonResponse[CheckLoginIdData],
    status_code=status.HTTP_200_OK,
    summary="로그인 ID 중복 확인",
    description="로그인 ID의 사용 가능 여부를 확인합니다.",
)
def check_login_id(
    login_id: Annotated[
        str,
        Query(
            min_length=4,
            max_length=50,
            pattern=LOGIN_ID_PATTERN,
            description="중복 확인할 로그인 ID",
        ),
    ],
    service: AuthServiceDep,
) -> CommonResponse[CheckLoginIdData]:
    """로그인 ID 사용 가능 여부를 반환한다."""

    result = service.check_login_id(
        login_id=login_id,
    )

    message = (
        "사용 가능한 아이디입니다."
        if result.is_available
        else "이미 사용 중인 아이디입니다."
    )

    return success_response(
        message=message,
        data=result,
        status_code=status.HTTP_200_OK,
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
