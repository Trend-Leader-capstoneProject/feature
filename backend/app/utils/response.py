from typing import TypeVar

from app.schemas.common_schema import CommonResponse

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
