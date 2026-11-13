"""Passing controls establish SDK/HTTP premises independently of missing C2."""

import importlib
import os
import socket
import subprocess
from importlib.metadata import version
from pathlib import Path

import openai
import pytest
from support import (
    API_KEY,
    CONNECTION_CASES,
    HTTP_CASES,
    OPTIONS,
    assert_request,
    assert_response,
    sdk_client,
)


def test_sdk_success_control(endpoint, http_client, sdk_responses):
    assert version("openai") == "3.50.0"
    with sdk_client(http_client) as client:
        assert client.max_retries == 0
        result = client.responses.create(**OPTIONS)
    assert_request(endpoint)
    assert_response(result, endpoint.payload)
    assert sdk_responses == [result]
    assert result is sdk_responses[0]


def test_existing_package_import_control():
    # __init__ re-exports pure S0 helpers: ordinary imports must remain allowed.
    package = importlib.import_module("app.responses_web_search")
    assert package.__file__.endswith("__init__.py")


@pytest.mark.parametrize("status,sdk_error,code", HTTP_CASES)
def test_sdk_http_error_control(endpoint, http_client, status, sdk_error, code):
    endpoint.status = status
    with sdk_client(http_client) as client:
        with pytest.raises(sdk_error) as caught:
            client.responses.create(**OPTIONS)
    assert isinstance(caught.value, openai.APIStatusError)
    assert caught.value.status_code == status
    assert_request(endpoint)


@pytest.mark.parametrize("transport_error,sdk_error,code", CONNECTION_CASES)
def test_sdk_connection_control(
    endpoint, http_client, transport_error, sdk_error, code,
):
    endpoint.transport_error = transport_error
    with sdk_client(http_client) as client:
        with pytest.raises(sdk_error) as caught:
            client.responses.create(**OPTIONS)
    assert type(caught.value) is sdk_error
    assert_request(endpoint)
    assert issubclass(openai.APITimeoutError, openai.APIConnectionError)


@pytest.mark.parametrize("strict", [False, True])
def test_sdk_response_validation_control(endpoint, http_client, strict):
    # Malformed response does not necessarily fail in the default construction path.
    endpoint.payload = {"id": "resp_malformed", "output": {"unexpected": True}}
    with sdk_client(http_client, _strict_response_validation=strict) as client:
        if strict:
            with pytest.raises(openai.APIResponseValidationError) as caught:
                client.responses.create(**OPTIONS)
            assert not isinstance(caught.value, openai.APIStatusError)
        else:
            client.responses.create(**OPTIONS)
    assert_request(endpoint)


def test_sdk_resource_strict_injection_control(endpoint, http_client, monkeypatch):
    """The R-04 resource wrapper must configure the actual SDK client."""
    original_create = openai.resources.responses.Responses.create

    def strict_create(resource, *args, **kwargs):
        resource._client._strict_response_validation = True
        return original_create(resource, *args, **kwargs)

    endpoint.payload = {"id": "resp_malformed", "output": {"unexpected": True}}
    monkeypatch.setattr(openai.resources.responses.Responses, "create", strict_create)
    with sdk_client(http_client) as client:
        assert client.responses._client is client
        assert client._strict_response_validation is False
        with pytest.raises(openai.APIResponseValidationError) as caught:
            client.responses.create(**OPTIONS)
        assert client._strict_response_validation is True
        assert caught.value.status_code == 200
        assert not isinstance(caught.value, openai.APIStatusError)
    assert_request(endpoint)


def test_retry_counter_detects_sdk_default(endpoint, http_client, monkeypatch):
    """Sensitivity control: default retries really cause three Mock sends."""
    endpoint.status = 429
    monkeypatch.setattr("openai._base_client.time.sleep", lambda _: None)
    with openai.OpenAI(api_key=API_KEY, http_client=http_client) as client:
        assert client.max_retries == 2
        with pytest.raises(openai.RateLimitError):
            client.responses.create(**OPTIONS)
    assert len(endpoint.calls) == 3


def test_isolation_controls(isolated_io):
    assert set(os.environ) <= {"PYTEST_CURRENT_TEST"}
    assert os.environ.get("OPENAI_API_KEY") is None
    assert Path(__file__).read_text(encoding="utf-8")  # Normal reads stay allowed.
    for probe in (
        lambda: socket.getaddrinfo("c2.invalid", 443),
        lambda: socket.create_connection(("c2.invalid", 443)),
        lambda: Path(".env.c2-never-read").read_text(),
        lambda: subprocess.Popen(["c2-never-executed"]),
    ):
        with pytest.raises(AssertionError, match="C2 external effect forbidden"):
            probe()
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="C2 external effect forbidden"):
            sock.connect(("127.0.0.1", 9))
    isolated_io.extend(["blocked"] * 5)
    for name in ("app.db.c2_probe", "redis", "dotenv"):
        with pytest.raises(AssertionError, match="C2 .* import forbidden"):
            importlib.import_module(name)
