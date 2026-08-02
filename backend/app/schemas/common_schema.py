from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class CommonResponse(BaseModel, Generic[DataT]):
    """Trend Leader 공통 성공 응답 Schema."""

    success: Literal[True] = True
    status_code: int = Field(serialization_alias="statusCode")
    message: str
    data: DataT
