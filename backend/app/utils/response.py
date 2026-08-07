from typing import Any, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.schemas.common_schema import CommonResponse
from app.schemas.error_schema import ErrorResponse

DataT = TypeVar("DataT")


def success_response(
    message: str,
    data: DataT,
    status_code: int = 200,
) -> CommonResponse[DataT]:
    """공통 성공 응답 모델을 생성한다."""

    return CommonResponse[DataT](
        status_code=status_code,
        message=message,
        data=data,
    )

def error_response(
    message: str,
    status_code: int,
    data: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """공통 오류 응답을 생성한다."""

    response = ErrorResponse(
        status_code=status_code,
        message=message,
        data=data,
    )

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            response,
            by_alias=True,
        ),
        headers=headers,
    )