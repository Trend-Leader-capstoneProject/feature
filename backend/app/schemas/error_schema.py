from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationErrorItem(BaseModel):
    """요청 검증 실패의 개별 오류 정보."""

    field: str
    message: str
    error_type: str = Field(
        serialization_alias="type",
    )


class ValidationErrorData(BaseModel):
    """요청 검증 실패 상세 데이터."""

    errors: list[ValidationErrorItem]


class ErrorResponse(BaseModel):
    """Trend Leader 공통 오류 응답 Schema."""

    success: Literal[False] = False
    status_code: int = Field(
        serialization_alias="statusCode",
    )
    message: str
    data: Any | None = None
