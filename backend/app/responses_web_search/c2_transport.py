"""Responses 단일 요청의 설정·전송·제한된 실패 경계."""

import math
from typing import Literal

import httpx2
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)
from openai.types.responses import Response

C2ErrorCode = Literal[
    "INVALID_CONFIGURATION",
    "TIMEOUT",
    "CONNECTION_ERROR",
    "AUTHENTICATION_FAILED",
    "PERMISSION_DENIED",
    "RATE_LIMITED",
    "UPSTREAM_SERVER_ERROR",
    "REQUEST_REJECTED",
    "SDK_RESPONSE_INVALID",
]


class C2TransportError(Exception):
    """본문·인증 정보·SDK 오류 원문을 포함하지 않는 내부 실패."""

    def __init__(self, code: C2ErrorCode) -> None:
        self.code = code
        super().__init__("C2 response request failed")


def request_response(
    *,
    api_key: str,
    model: str,
    input_text: str,
    timeout: float,
    http_client: httpx2.Client,
) -> Response:
    """재시도 없이 전송하고 SDK Response를 변경하지 않고 반환한다."""
    if (
        not isinstance(api_key, str) or not api_key.strip()
        or not isinstance(model, str) or not model.strip()
        or not isinstance(input_text, str) or not input_text.strip()
        or isinstance(timeout, bool) or not isinstance(timeout, (int, float))
        or timeout <= 0 or not math.isfinite(timeout)
    ):
        raise C2TransportError("INVALID_CONFIGURATION")

    try:
        with OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=timeout,
            http_client=http_client,
        ) as client:
            return client.responses.create(
                model=model,
                input=input_text,
                store=False,
                stream=False,
                tools=[{"type": "web_search"}],
                tool_choice="required",
                max_tool_calls=1,
                include=["web_search_call.action.sources"],
            )
    except APITimeoutError:
        # APITimeoutError는 APIConnectionError의 하위 타입이다.
        raise C2TransportError("TIMEOUT") from None
    except APIConnectionError:
        raise C2TransportError("CONNECTION_ERROR") from None
    except APIResponseValidationError:
        raise C2TransportError("SDK_RESPONSE_INVALID") from None
    except APIStatusError as error:
        code: C2ErrorCode
        if error.status_code == 401:
            code = "AUTHENTICATION_FAILED"
        elif error.status_code == 403:
            code = "PERMISSION_DENIED"
        elif error.status_code == 429:
            code = "RATE_LIMITED"
        elif 500 <= error.status_code < 600:
            code = "UPSTREAM_SERVER_ERROR"
        elif 400 <= error.status_code < 500:
            code = "REQUEST_REJECTED"
        else:
            raise
        # 일반 traceback의 원문 표시는 억제하지만 __context__는 남을 수 있다.
        raise C2TransportError(code) from None
