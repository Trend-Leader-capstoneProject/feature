from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class CommonResponse(BaseModel, Generic[DataT]):
    """Trend Leader 공통 성공 응답 Schema."""

    success: bool
    status_code: int = Field(serialization_alias="statusCode")
    message: str
    data: DataT
