"""D0-01~03: optional C2 output limit; existing Mock connection stays intact.

SDK 3.50.0 declares Optional[int] | Omit; the server minimum is integer 16
per the Responses create API reference confirmed in the D0 review:
https://developers.openai.com/api/reference/resources/responses/methods/create
"""

import importlib
import json
from importlib.metadata import version

import pytest
from support import (
    API_KEY,
    INPUT,
    MODEL,
    OPTIONS,
    TIMEOUT,
    assert_request,
    assert_response,
    sdk_client,
)


def invoke(http_client, **options):
    module = importlib.import_module("app.responses_web_search.c2_transport")
    return module.request_response(
        api_key=API_KEY, model=MODEL, input_text=INPUT,
        timeout=TIMEOUT, http_client=http_client, **options,
    )


@pytest.mark.parametrize("limit", [16, 4096], ids=["api-minimum", "planned-limit"])
def test_d0_sdk_output_limit_control(endpoint, http_client, limit):
    """Real SDK serialization through MockTransport, independent of C2."""
    assert version("openai") == "3.50.0"
    assert version("httpx2") == "2.16.0"
    with sdk_client(http_client) as client:
        assert client.max_retries == 0
        result = client.responses.create(**OPTIONS, max_output_tokens=limit)
    assert_request(endpoint)
    assert_response(result, endpoint.payload)
    body = json.loads(endpoint.calls[0].content)
    assert body == {**OPTIONS, "max_output_tokens": limit}
    assert type(body["max_output_tokens"]) is int


@pytest.mark.parametrize("options", [{}, {"max_output_tokens": None}],
                         ids=["omitted", "explicit-none"])
def test_d0_01_absent_limit_preserves_request(endpoint, http_client, options):
    result = invoke(http_client, **options)
    assert_response(result, endpoint.payload)
    assert_request(endpoint)
    assert json.loads(endpoint.calls[0].content) == OPTIONS


@pytest.mark.parametrize("limit", [16, 4096], ids=["api-minimum", "planned-limit"])
def test_d0_02_limit_reaches_sdk_without_policy_changes(
    endpoint, http_client, monkeypatch, limit,
):
    from openai.resources.responses import Responses

    observed_retries = []
    original = Responses.create

    def observe(resource, *args, **kwargs):
        observed_retries.append(resource._client.max_retries)
        return original(resource, *args, **kwargs)

    monkeypatch.setattr(Responses, "create", observe)
    result = invoke(http_client, max_output_tokens=limit)
    assert_response(result, endpoint.payload)
    assert_request(endpoint)
    assert observed_retries == [0]
    body = json.loads(endpoint.calls[0].content)
    assert body == {**OPTIONS, "max_output_tokens": limit}
    assert type(body["max_output_tokens"]) is int


@pytest.mark.parametrize("value", [
    True, False, 0, -1, 15, 4096.0, 1.5, "4096", [], float("inf"), float("nan"),
], ids=["true", "false", "zero", "negative", "below-api-minimum",
        "integral-float", "fraction", "string", "list", "infinity", "nan"])
def test_d0_03_invalid_limit_rejected_before_sdk(
    endpoint, http_client, monkeypatch, value, caplog, capsys,
):
    module = importlib.import_module("app.responses_web_search.c2_transport")
    sdk_attempts = []

    def forbidden_client(*args, **kwargs):
        sdk_attempts.append("client")
        raise AssertionError("Invalid configuration reached SDK construction")

    monkeypatch.setattr(module, "OpenAI", forbidden_client)
    try:
        with pytest.raises(module.C2TransportError) as caught:
            invoke(http_client, max_output_tokens=value)
        assert caught.value.code == "INVALID_CONFIGURATION"
        captured = capsys.readouterr()
        visible = str(caught.value) + repr(caught.value) + caplog.text
        visible += captured.out + captured.err
        assert API_KEY not in visible
        assert "Bearer " not in visible
    finally:
        assert sdk_attempts == []
        assert endpoint.calls == []
