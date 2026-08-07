from collections.abc import Mapping
from typing import Any

from fastapi import status


class ApplicationException(Exception):
    """예상 가능한 애플리케이션 오류의 공통 기반 예외."""
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "서버 오류가 발생했습니다."
    
    def __init__(
        self,
        message: str | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.data = data
        self.headers = headers

        super().__init__(self.message)


class BadRequestException(ApplicationException):
    """요청 내용이 비즈니스 규칙에 맞지 않을 때 발생한다."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "입력값이 올바르지 않습니다."


class UnauthorizedException(ApplicationException):
    """인증 정보가 없거나 유효하지 않을 때 발생한다."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "로그인이 필요합니다."

    def __init__(
        self,
        message: str | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            data=data,
            headers=headers or {"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(ApplicationException):
    """인증된 사용자가 요청 권한을 갖지 않을 때 발생한다."""

    status_code = status.HTTP_403_FORBIDDEN
    default_message = "접근 권한이 없습니다."


class NotFoundException(ApplicationException):
    """요청한 리소스를 찾을 수 없을 때 발생한다."""

    status_code = status.HTTP_404_NOT_FOUND
    default_message = "요청한 데이터를 찾을 수 없습니다."


class ConflictException(ApplicationException):
    """현재 리소스 상태와 요청이 충돌할 때 발생한다."""

    status_code = status.HTTP_409_CONFLICT
    default_message = "이미 존재하는 데이터입니다."