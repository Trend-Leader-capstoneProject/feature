"""Proposed C2 public contract. No implementation, fallback or xfail."""

import importlib
import inspect
import traceback

import openai
import pytest
from support import (
    API_KEY,
    CONNECTION_CASES,
    HTTP_CASES,
    INPUT,
    MARKER,
    MODEL,
    TIMEOUT,
    assert_request,
    assert_response,
)


def transport_module():
    # Import inside the test: collection and SDK controls remain independently usable.
    return importlib.import_module("app.responses_web_search.c2_transport")


def invoke(module, http_client, **overrides):
    args = dict(
        api_key=API_KEY, model=MODEL, input_text=INPUT,
        timeout=TIMEOUT, http_client=http_client,
    )
    args.update(overrides)
    return module.request_response(**args)


def assert_safe(error, code, caplog, capsys):
    assert error.code == code
    captured = capsys.readouterr()
    visible = "\n".join((
        str(error), repr(error), "".join(traceback.format_exception(error)),
        caplog.text, captured.out, captured.err,
    ))
    for secret in (API_KEY, MARKER, "Bearer "):
        assert secret not in visible


def test_r01_original_sdk_response_and_request(endpoint, http_client, sdk_responses):
    module = transport_module()
    assert (
        inspect.signature(module.request_response).parameters["timeout"].default
        is inspect.Parameter.empty
    )
    result = invoke(module, http_client)
    assert sdk_responses == [result]
    assert result is sdk_responses[0]
    assert_response(result, endpoint.payload)
    assert_request(endpoint)


@pytest.mark.parametrize("status,sdk_error,code", HTTP_CASES)
def test_r02_r04_http_no_retry_and_classification(
    endpoint, http_client, status, sdk_error, code, caplog, capsys,
):
    endpoint.status = status
    module = transport_module()
    with pytest.raises(module.C2TransportError) as caught:
        invoke(module, http_client)
    assert_request(endpoint)
    assert_safe(caught.value, code, caplog, capsys)


@pytest.mark.parametrize("transport_error,sdk_error,code", CONNECTION_CASES)
def test_r03_connection_no_retry_and_safe_failure(
    endpoint, http_client, transport_error, sdk_error, code, caplog, capsys,
):
    endpoint.transport_error = transport_error
    module = transport_module()
    with pytest.raises(module.C2TransportError) as caught:
        invoke(module, http_client)
    assert_request(endpoint)
    assert_safe(caught.value, code, caplog, capsys)


def test_r04_sdk_validation_error_is_separate(
    endpoint, http_client, monkeypatch, caplog, capsys,
):
    module = transport_module()
    original_create = openai.resources.responses.Responses.create

    def strict_create(resource, *args, **kwargs):
        # Exercise real SDK validation, not a fabricated HTTP status exception.
        # Test-only injection: strict mode is NOT required of production C2.
        resource._client._strict_response_validation = True
        return original_create(resource, *args, **kwargs)

    endpoint.payload = {"id": MARKER, "output": {"bad": MARKER}}
    monkeypatch.setattr(openai.resources.responses.Responses, "create", strict_create)
    with pytest.raises(module.C2TransportError) as caught:
        invoke(module, http_client)
    assert_request(endpoint)
    assert_safe(caught.value, "SDK_RESPONSE_INVALID", caplog, capsys)


@pytest.mark.parametrize("overrides", [
    {"model": ""}, {"model": " \t"},
    {"input_text": ""}, {"input_text": " \n"},
    *({"timeout": value} for value in (0, -1, float("inf"), -float("inf"),
                                     float("nan"), None)),
], ids=["model-empty", "model-whitespace", "input-empty", "input-whitespace",
        "timeout-zero", "timeout-negative", "timeout-inf", "timeout-neg-inf",
        "timeout-nan", "timeout-missing-value"])
def test_r05_invalid_configuration_before_http(
    endpoint, http_client, overrides, caplog, capsys,
):
    module = transport_module()
    with pytest.raises(module.C2TransportError) as caught:
        invoke(module, http_client, **overrides)
    assert endpoint.calls == []
    assert_safe(caught.value, "INVALID_CONFIGURATION", caplog, capsys)


def test_r01_explicit_positive_timeout_overrides_http_client(endpoint, http_client):
    # The 60-second fixture must not become a hardcoded transport default.
    module = transport_module()
    result = invoke(module, http_client, timeout=2.5)
    assert_response(result, endpoint.payload)
    assert_request(endpoint, timeout=2.5)
