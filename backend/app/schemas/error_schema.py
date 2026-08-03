from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Trend Leader 공통 오류 응답 Schema."""

    success: Literal[False] = False
    status_code: int = Field(
        serialization_alias="statusCode",
    )
    message: str
    data: Any | None = None
