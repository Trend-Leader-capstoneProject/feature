"""SDK 응답의 원본 증거를 S1에 전달하는 메모리 전용 직렬화 경계."""

from openai.types.responses import Response


class C1ConversionError(ValueError):
    """응답 본문이나 SDK 예외 원문을 포함하지 않는 제한된 변환 실패."""


def convert_response(response: Response) -> dict[str, object]:
    """전체 응답을 보존하며 검색 성공·후보 유효성은 판단하지 않는다."""
    if not isinstance(response, Response):
        raise C1ConversionError("C1 response conversion failed")

    try:
        return response.to_dict(
            mode="json",
            use_api_names=True,
            exclude_unset=True,
            exclude_defaults=False,
            exclude_none=False,
            # SDK 직렬화 경고에 원본 입력값이 포함되는 것을 방지한다.
            warnings=False,
        )
    except (ValueError, TypeError, RecursionError):
        # PydanticSerializationError는 ValueError의 하위 타입이다.
        # 표준 traceback에 SDK 오류 원문을 연결하지 않는다.
        raise C1ConversionError("C1 response conversion failed") from None
