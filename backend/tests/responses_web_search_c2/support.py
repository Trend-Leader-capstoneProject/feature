"""Independent HTTP fixtures and SDK assertions, never a C2 substitute."""

import json
from copy import deepcopy

import httpx2
import openai
from openai.types.responses import Response

API_KEY = "test-only-invalid-c2-key"
MARKER = "SYNTHETIC_C2_SECRET_BODY_OR_EXCEPTION"
MODEL = "caller-supplied-test-model"
INPUT = "Caller supplied search input — 합성 전송 검증"
TIMEOUT = 60.0  # Test value only; no production default is established.
OPTIONS = {
    "model": MODEL, "input": INPUT, "store": False, "stream": False,
    "tools": [{"type": "web_search"}], "tool_choice": "required",
    "max_tool_calls": 1, "include": ["web_search_call.action.sources"],
}
HTTP_CASES = [
    (400, openai.BadRequestError, "REQUEST_REJECTED"),
    (401, openai.AuthenticationError, "AUTHENTICATION_FAILED"),
    (403, openai.PermissionDeniedError, "PERMISSION_DENIED"),
    (404, openai.NotFoundError, "REQUEST_REJECTED"),
    (408, openai.APIStatusError, "REQUEST_REJECTED"),
    (409, openai.ConflictError, "REQUEST_REJECTED"),
    (418, openai.APIStatusError, "REQUEST_REJECTED"),
    (422, openai.UnprocessableEntityError, "REQUEST_REJECTED"),
    (429, openai.RateLimitError, "RATE_LIMITED"),
    (500, openai.InternalServerError, "UPSTREAM_SERVER_ERROR"),
    (503, openai.InternalServerError, "UPSTREAM_SERVER_ERROR"),
]
CONNECTION_CASES = [
    (httpx2.ReadTimeout, openai.APITimeoutError, "TIMEOUT"),
    (httpx2.ConnectError, openai.APIConnectionError, "CONNECTION_ERROR"),
]


def original_response():
    # Deliberately not a valid candidate: C2 must not parse or repair output.
    return {
        "id": "resp_c2", "object": "response", "created_at": 1794528000,
        "model": MODEL, "status": "completed", "parallel_tool_calls": False,
        "tool_choice": "required", "tools": [{"type": "web_search"}],
        "output": [
            {"id": "ws_1", "type": "web_search_call", "status": "completed",
             "action": {"type": "search", "query": "independent query",
                        "sources": [{"type": "url", "url": "https://example.com"}]}},
            {"id": "rs_1", "type": "reasoning", "summary": []},
            {"id": "msg_1", "type": "message", "role": "assistant",
             "status": "completed", "phase": "final_answer",
             "content": [{"type": "output_text", "text": "not candidate JSON",
                          "annotations": []}]},
        ],
    }


class MockEndpoint:
    def __init__(self, status=200, transport_error=None, payload=None):
        self.calls = []
        self.status = status
        self.transport_error = transport_error
        self.payload = deepcopy(payload if payload is not None else original_response())

    def handle(self, request):
        self.calls.append(request)
        assert request.method == "POST"
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        if self.transport_error:
            raise self.transport_error(MARKER, request=request)
        if self.status != 200:
            return httpx2.Response(
                self.status, json={"error": {"message": MARKER, "type": "test"}},
                headers={"retry-after": "0", "x-should-retry": "true"},
            )
        return httpx2.Response(200, json=self.payload)


def assert_request(endpoint, timeout=TIMEOUT):
    assert len(endpoint.calls) == 1
    request = endpoint.calls[0]
    body = json.loads(request.content)
    for key, value in OPTIONS.items():
        assert key in body
        assert body[key] == value
    assert body["store"] is False
    assert body["stream"] is False
    assert "background" not in body or body["background"] is False
    assert request.extensions["timeout"] == dict.fromkeys(
        ("connect", "read", "write", "pool"), timeout,
    )


def assert_response(response, original):
    assert isinstance(response, Response)
    assert response.to_dict()["output"] == original["output"]


def sdk_client(http_client, **kwargs):
    return openai.OpenAI(
        api_key=API_KEY, http_client=http_client, timeout=TIMEOUT,
        max_retries=0, **kwargs,
    )
