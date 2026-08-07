import logging
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import HTTPExceptionHandler

from app.core.exceptions import ApplicationException
from app.schemas.error_schema import (
    ValidationErrorData,
    ValidationErrorItem,
)
from app.utils.response import error_response

logger = logging.getLogger(__name__)

HTTP_ERROR_MESSAGES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "입력값이 올바르지 않습니다.",
    status.HTTP_401_UNAUTHORIZED: "로그인이 필요합니다.",
    status.HTTP_403_FORBIDDEN: "접근 권한이 없습니다.",
    status.HTTP_404_NOT_FOUND: "요청한 데이터를 찾을 수 없습니다.",
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        "허용되지 않은 요청 방식입니다."
    ),
    status.HTTP_409_CONFLICT: "이미 존재하는 데이터입니다.",
    status.HTTP_422_UNPROCESSABLE_CONTENT: (
        "요청 데이터가 올바르지 않습니다."
    ),
    status.HTTP_503_SERVICE_UNAVAILABLE: (
        "서비스를 사용할 수 없습니다."
    ),
}


def _get_http_error_message(
    status_code: int,
) -> str:
    """HTTP 상태 코드에 대응하는 공통 오류 메시지를 반환한다."""

    return HTTP_ERROR_MESSAGES.get(
        status_code,
        "요청을 처리할 수 없습니다.",
    )


def _create_validation_error_data(
    exc: RequestValidationError,
) -> ValidationErrorData:
    """FastAPI 요청 검증 오류를 공통 오류 데이터로 변환한다."""

    errors: list[ValidationErrorItem] = []

    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(
            str(value)
            for value in location
        )

        errors.append(
            ValidationErrorItem(
                field=field,
                message=str(
                    error.get(
                        "msg",
                        "Invalid value",
                    )
                ),
                error_type=str(
                    error.get(
                        "type",
                        "validation_error",
                    )
                ),
            )
        )

    return ValidationErrorData(
        errors=errors,
    )


async def application_exception_handler(
    _request: Request,
    exc: ApplicationException,
) -> JSONResponse:
    """예상 가능한 애플리케이션 예외를 공통 응답으로 변환한다."""

    return error_response(
        message=exc.message,
        status_code=exc.status_code,
        data=exc.data,
        headers=exc.headers,
    )


async def request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Pydantic 요청 검증 오류를 422 공통 응답으로 변환한다."""

    return error_response(
        message=HTTP_ERROR_MESSAGES[
            status.HTTP_422_UNPROCESSABLE_CONTENT
        ],
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        data=_create_validation_error_data(exc),
    )


async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """FastAPI와 Starlette의 HTTP 예외를 공통 응답으로 변환한다."""

    return error_response(
        message=_get_http_error_message(
            exc.status_code,
        ),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """처리되지 않은 서버 예외를 기록하고 500 응답을 반환한다."""

    logger.error(
        "Unhandled exception occurred: method=%s path=%s",
        request.method,
        request.url.path,
        exc_info=(
            type(exc),
            exc,
            exc.__traceback__,
        ),
    )

    return error_response(
        message="서버 오류가 발생했습니다.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(
    application: FastAPI,
) -> None:
    """Trend Leader 공통 예외 처리기를 애플리케이션에 등록한다."""

    application.add_exception_handler(
        ApplicationException,
        cast(
            HTTPExceptionHandler,
            application_exception_handler,
        ),
    )
    application.add_exception_handler(
        RequestValidationError,
        cast(
            HTTPExceptionHandler,
            request_validation_exception_handler,
        ),
    )
    application.add_exception_handler(
        StarletteHTTPException,
        cast(
            HTTPExceptionHandler,
            http_exception_handler,
        ),
    )
    application.add_exception_handler(
        Exception,
        cast(
            HTTPExceptionHandler,
            unhandled_exception_handler,
        ),
    )