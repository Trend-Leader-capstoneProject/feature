from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class CommonResponse(BaseModel, Generic[DataT]):
    """Trend Leader 공통 성공 응답 Schema."""

    success: Literal[True] = True
    status_code: int = Field(serialization_alias="statusCode")
    message: str
    data: DataT

class ErrorResponse(BaseModel):
    """Trend Leader 공통 오류 응답 Schema."""

    success: Literal[False] = False
    status_code: int = Field(
        serialization_alias="statusCode",
    )
    message: str
    data: Any | None = None