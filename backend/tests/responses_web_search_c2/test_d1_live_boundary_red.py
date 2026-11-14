"""Gate D1-A offline Red. Run ONLY this file with C2 --confcutdir.

Proposed internal interfaces (not public/Frozen contracts):
  d1_cli.main(argv=None, *, stdin, stdout, stderr, execution_at=None,
              http_transport=None) -> int
  d1_live_preview.run_live_preview(*, plan, execute_live=False,
      interactive=False, confirmation=None, api_key=None, http_transport=None)
      -> JSON-compatible dict
The service independently checks all three approval conditions before C2.
CLI uses stdin/stdout TTY, exact PHRASE on a separate input line, and reads a
key from its environment only after approval. No key CLI argument is accepted.
The transport injection is a test seam, not a CLI option or new framework.
CLI prints a preflight by default; nonapproval never enters a request path.
New LIVE/usage fields below are proposals, not changes to SDK_MOCK or Frozen.
CONFIRMED means completed search evidence in the response, never verification
of source truth or popularity. Timeout means unknown remote processing outcome.

All authorization/key inputs here are synthetic. Never invoke as a live CLI.
"""

import dataclasses
import importlib
import json
import logging
import os
import socket
from importlib.metadata import version
from unittest.mock import Mock

import httpx2
import pytest
from d1_support import (
    CLI,
    LIVE,
    PHRASE,
    USAGE,
    Terminal,
    assert_flow,
    assert_no_authorization_header,
    assert_request,
    assert_safe,
    cli,
    d1_isolation as guarded_io,
    expected_flow,
    invoke,
    no_dispatch as blocked_dispatch,
    payload_for,
    plan,
    product,
)
from openai.types.responses import Response
from support import API_KEY, MARKER, MockEndpoint
from test_sdk_mock_preview_red import pipeline as observed_pipeline

# Register reused fixtures under local names without copying their implementation.
d1_isolation = guarded_io
no_dispatch = blocked_dispatch
pipeline = observed_pipeline

pytestmark = pytest.mark.usefixtures("d1_isolation")


@pytest.fixture(autouse=True)
def verbose_logs(caplog):
    # Catch sensitive HTTP/SDK debug logs too, not only warnings.
    caplog.set_level(logging.DEBUG)


def test_d1_isolation_control(isolated_io, d1_isolation):
    # C2 replaced it before pytest added its own current-test marker.
    assert set(os.environ) <= {"PYTEST_CURRENT_TEST"}
    with pytest.raises(AssertionError, match="C2 external effect"):
        socket.create_connection(("example.invalid", 443))
    isolated_io.append("blocked")
    with pytest.raises(AssertionError, match="D1 real HTTP"):
        httpx2.HTTPTransport.handle_request(None, None)
    d1_isolation.append("real-http")
    for name in ("app.d1_forbidden_writer_probe", "app.external_trends",
                 "sqlalchemy", "redis"):
        with pytest.raises(AssertionError, match="D1 operational import"):
            importlib.import_module(name)
        d1_isolation.append("operational-import")
    with pytest.raises(AssertionError, match="D1 file write"):
        open("d1-must-never-be-created.txt", "w")
    d1_isolation.append("file-write")
    with pytest.raises(AssertionError, match="C2 external effect"):
        open(".env")
    isolated_io.append("blocked")


def test_d1_dispatch_guard_control(no_dispatch):
    transport = importlib.import_module("app.responses_web_search.c2_transport")
    with pytest.raises(AssertionError, match="D1 unauthorized dispatch"):
        transport.request_response()
    assert no_dispatch == ["dispatch"]
    no_dispatch.clear()  # Only the sensitivity control expects a blocked call.


def test_d1_authorization_header_guard_control():
    safe = {"publish_authorization": "NONE",
            "candidates": [{"publish_authorization": "NONE"}]}
    assert_no_authorization_header(repr(safe))
    assert_no_authorization_header(json.dumps(safe))
    for header in (
        "Authorization: Basic synthetic-credentials",
        "authorization : synthetic-credentials",
        '"AUTHORIZATION": "synthetic-credentials"',
        "{'aUtHoRiZaTiOn': 'synthetic-credentials'}",
        "('Authorization', 'synthetic-credentials')",
        "{b'authorization': b'synthetic-credentials'}",
    ):
        with pytest.raises(AssertionError, match="Authentication header exposed"):
            assert_no_authorization_header(header)


@pytest.mark.parametrize("case", ["ready", "rejected", "no-search", "empty"])
def test_d1_fixture_control(case, endpoint, http_client):
    """Check new fixture assumptions through real C2/C1/S1/S0, no D1 substitute."""
    from app.responses_web_search.c1_adapter import convert_response
    from app.responses_web_search.c2_transport import request_response
    from app.responses_web_search.normalizer import normalize_response
    from app.responses_web_search.types import SearchRunConfig

    assert version("openai") == "3.50.0"
    assert version("httpx2") == "2.16.0"
    endpoint.payload = payload_for(case)
    endpoint.payload["usage"] = USAGE
    approved = plan()
    response = request_response(
        api_key=API_KEY, model=approved.config.model, input_text=approved.input_text,
        timeout=approved.config.timeout, max_output_tokens=4096,
        http_client=http_client,
    )
    converted = convert_response(response)
    assert {key: converted["usage"][key] for key in USAGE} == USAGE
    normalized = normalize_response(converted, SearchRunConfig())
    assert normalized.outcome == ("REJECTED" if case == "rejected" else "NORMALIZED")
    assert_request(endpoint, approved)
    assert http_client.is_closed


@pytest.mark.parametrize("case,code", [
    (401, "AUTHENTICATION_FAILED"), (429, "RATE_LIMITED"),
    (503, "UPSTREAM_SERVER_ERROR"), ("timeout", "TIMEOUT"),
    ("c1", "C1_CONVERSION_FAILED"),
])
def test_d1_failure_fixture_control(case, code, endpoint, http_client, monkeypatch):
    """Prove fault injection independently of the absent D1 interfaces."""
    from app.responses_web_search.c1_adapter import C1ConversionError, convert_response
    from app.responses_web_search.c2_transport import C2TransportError, request_response

    endpoint.payload = payload_for("ready")
    if isinstance(case, int):
        endpoint.status = case
    elif case == "timeout":
        endpoint.transport_error = httpx2.ReadTimeout
    else:
        monkeypatch.setattr(Response, "to_dict", Mock(side_effect=ValueError(MARKER)))
    approved = plan()
    error_type = C1ConversionError if case == "c1" else C2TransportError
    with pytest.raises(error_type) as caught:
        response = request_response(
            api_key=API_KEY, model=approved.config.model,
            input_text=approved.input_text, timeout=approved.config.timeout,
            max_output_tokens=4096, http_client=http_client,
        )
        convert_response(response)
    if case != "c1":
        assert caught.value.code == code
    assert_request(endpoint, approved)
    assert http_client.is_closed


@pytest.mark.parametrize("name", [CLI, LIVE])
def test_d1_01_import_has_no_dispatch(name, no_dispatch):
    product(name)  # Import and reload are both guarded.
    product(name)
    assert no_dispatch == []


@pytest.mark.parametrize("key_present", [False, True])
def test_d1_01_default_cli_is_preflight_only(
    key_present, monkeypatch, no_dispatch, caplog, capsys,
):
    if key_present:
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", API_KEY)
    endpoint = MockEndpoint()
    code, stdin, out, err = cli(product(CLI), endpoint)
    assert code == 0
    assert stdin.reads == 0
    assert endpoint.calls == []
    assert "PREFLIGHT_VALIDATED" in out
    assert json.loads(out)["live_request_allowed"] is False
    captured = capsys.readouterr()
    assert API_KEY not in out + err + caplog.text + captured.out + captured.err


@pytest.mark.parametrize("stdin,stdout", [
    (Terminal(""), Terminal()),
    (Terminal("wrong\n"), Terminal()),
    (Terminal(" " + PHRASE + "\n"), Terminal()),
    (Terminal(PHRASE + "\n", tty=False), Terminal()),
    (Terminal(PHRASE + "\n"), Terminal(tty=False)),
    (Terminal(interrupt=EOFError), Terminal()),
    (Terminal(interrupt=KeyboardInterrupt), Terminal()),
], ids=["option-only-eof", "wrong", "not-exact", "stdin-pipe", "stdout-pipe",
        "eof-error", "cancel"])
def test_d1_02_cli_nonapproval_sends_zero(
    stdin, stdout, monkeypatch, no_dispatch, caplog, capsys,
):
    monkeypatch.setitem(os.environ, "OPENAI_API_KEY", API_KEY)
    endpoint = MockEndpoint()
    code, _, out, err = cli(
        product(CLI), endpoint, argv=("--execute-live",), stdin=stdin, stdout=stdout,
    )
    assert code != 0
    assert endpoint.calls == []
    captured = capsys.readouterr()
    visible = out + err + caplog.text + captured.out + captured.err
    assert API_KEY not in visible and "Bearer " not in visible


@pytest.mark.parametrize("overrides", [
    {"execute_live": False}, {"interactive": False},
    {"confirmation": None}, {"confirmation": "wrong"},
    {"confirmation": " " + PHRASE}, {"api_key": None},
], ids=["no-option", "noninteractive", "no-confirmation", "wrong-confirmation",
        "not-exact", "no-key"])
def test_d1_02_service_cannot_bypass_confirmation(overrides, no_dispatch):
    endpoint = MockEndpoint()
    approved = plan()
    before = dataclasses.asdict(approved)
    result = invoke(product(LIVE), endpoint, plan=approved, **overrides)
    assert endpoint.calls == []
    assert result["status"] in {"PREFLIGHT_VALIDATED", "LIVE_NOT_AUTHORIZED",
                                "BLOCKED_CONFIG"}
    assert dataclasses.asdict(approved) == before
    assert approved.live_request_allowed is False


def test_d1_02_service_defaults_cannot_dispatch(no_dispatch):
    result = product(LIVE).run_live_preview(plan=plan())
    assert result["status"] in {"PREFLIGHT_VALIDATED", "LIVE_NOT_AUTHORIZED"}


@pytest.mark.parametrize("usage", [USAGE, None], ids=["observed", "absent"])
def test_d1_03_04_05_07_10_authorized_mock_once(
    usage, pipeline, sdk_responses, caplog, capsys,
):
    endpoint = MockEndpoint(payload=payload_for("ready"))
    if usage is not None:
        endpoint.payload["usage"] = usage | {"untrusted_extra": MARKER}
    approved = plan()
    before = dataclasses.asdict(approved)
    preview = invoke(product(LIVE), endpoint, plan=approved)
    assert_request(endpoint, approved)
    assert_flow(pipeline, expected_flow("ready"))
    assert len(sdk_responses) == 1
    assert preview["status"] == "PREVIEW_READY"
    assert preview["search_execution"] == "CONFIRMED"
    assert preview["response_validation"] == "VALID"
    assert preview["tool_calls_observed"] == 1
    assert preview["usage"] == usage
    assert len(preview["candidates"]) == 1
    validated, _ = pipeline.results["validate"][0]
    for key, value in dataclasses.asdict(validated[0]).items():
        assert preview["candidates"][0][key] == value
    assert dataclasses.asdict(approved) == before
    assert approved.live_request_allowed is False
    assert_safe(preview, caplog, capsys)
    assert pipeline.clients and all(client.is_closed for client in pipeline.clients)


def test_d1_03_cli_exact_confirmation_once(monkeypatch, pipeline, caplog, capsys):
    monkeypatch.setitem(os.environ, "OPENAI_API_KEY", API_KEY)
    endpoint = MockEndpoint(payload=payload_for("ready"))
    code, stdin, out, err = cli(product(CLI), endpoint, argv=("--execute-live",))
    assert code == 0
    assert stdin.reads == 1
    assert PHRASE in out + err  # Human can see which phrase is required.
    assert "PREVIEW_READY" in out
    assert_request(endpoint, plan())
    assert_flow(pipeline, expected_flow("ready"))
    captured = capsys.readouterr()
    visible = out + err + caplog.text + captured.out + captured.err
    assert_no_authorization_header(visible)
    for marker in (API_KEY, MARKER, "Bearer "):
        assert marker not in visible


@pytest.mark.parametrize("case,code", [
    (401, "AUTHENTICATION_FAILED"), (429, "RATE_LIMITED"),
    (503, "UPSTREAM_SERVER_ERROR"), ("timeout", "TIMEOUT"),
    ("c1", "C1_CONVERSION_FAILED"),
])
def test_d1_06_09_error_stops_without_retry(
    case, code, pipeline, sdk_responses, monkeypatch, caplog, capsys,
):
    endpoint = MockEndpoint(payload=payload_for("ready"))
    if isinstance(case, int):
        endpoint.status = case
    elif case == "timeout":
        # Recorded before ReadTimeout: remote processing is UNKNOWN, not absent.
        endpoint.transport_error = httpx2.ReadTimeout
    else:
        monkeypatch.setattr(Response, "to_dict", Mock(side_effect=ValueError(MARKER)))
    preview = invoke(product(LIVE), endpoint)
    assert_request(endpoint, plan())  # Retry-sensitive endpoint has retry headers.
    assert_flow(pipeline, ["c2", "c1"] if case == "c1" else ["c2"])
    assert len(sdk_responses) == (1 if case == "c1" else 0)
    assert preview["reason_codes"] == [code]
    assert preview["status"] == (
        "INVALID_OR_INCOMPLETE_RESPONSE" if case == "c1" else "UPSTREAM_ERROR"
    )
    assert preview["search_execution"] == "UNKNOWN"
    assert preview["response_validation"] == "NOT_EVALUATED"
    assert preview["candidates"] == []
    assert preview["usage"] is None
    assert_safe(preview, caplog, capsys)
    assert pipeline.clients and all(client.is_closed for client in pipeline.clients)


@pytest.mark.parametrize("case,status,search", [
    ("rejected", "INVALID_OR_INCOMPLETE_RESPONSE", "CONFIRMED"),
    ("no-search", "SEARCH_NOT_EXECUTED", "NOT_CONFIRMED"),
    ("empty", "EMPTY_RESULT", "CONFIRMED"),
])
def test_d1_08_10_nonpublishable_outcomes(
    case, status, search, pipeline, caplog, capsys,
):
    endpoint = MockEndpoint(payload=payload_for(case))
    preview = invoke(product(LIVE), endpoint)
    assert_request(endpoint, plan())
    assert_flow(pipeline, expected_flow(case))
    assert preview["status"] == status
    assert preview["search_execution"] == search
    assert preview["candidates"] == []
    assert_safe(preview, caplog, capsys)


def test_d1_09_unvalidated_body_not_visible(pipeline, caplog, capsys):
    endpoint = MockEndpoint(payload=payload_for("bad-json"))
    endpoint.payload["output"][-1]["content"][0]["text"] = "RAW_D1_CONTENT"
    preview = invoke(product(LIVE), endpoint)
    assert_request(endpoint, plan())
    assert_flow(pipeline, ["c2", "c1", "normalize", "parse"])
    assert preview["candidates"] == []
    assert_safe(preview, caplog, capsys)


@pytest.mark.parametrize("case", ["http", "timeout", "c1", "raw"])
def test_d1_09_cli_failure_has_no_traceback_or_sensitive_text(
    case, monkeypatch, pipeline, caplog, capsys,
):
    monkeypatch.setitem(os.environ, "OPENAI_API_KEY", API_KEY)
    endpoint = MockEndpoint(payload=payload_for("ready"))
    if case == "http":
        endpoint.status = 401
    elif case == "timeout":
        endpoint.transport_error = httpx2.ReadTimeout
    elif case == "c1":
        monkeypatch.setattr(Response, "to_dict", Mock(side_effect=ValueError(MARKER)))
    else:
        endpoint.payload["output"][-1]["content"][0]["text"] = "RAW_D1_CONTENT"
    code, _, out, err = cli(product(CLI), endpoint, argv=("--execute-live",))
    assert code != 0
    assert_request(endpoint, plan())
    captured = capsys.readouterr()
    visible = out + err + caplog.text + captured.out + captured.err
    assert_no_authorization_header(visible)
    for marker in (API_KEY, MARKER, "Bearer ", "RAW_D1_CONTENT",
                   "Traceback (most recent call last)"):
        assert marker not in visible


def test_d1_09_key_cli_argument_rejected_without_echo(no_dispatch, caplog, capsys):
    endpoint = MockEndpoint()
    code, _, out, err = cli(product(CLI), endpoint, argv=("--api-key", API_KEY))
    assert code != 0
    assert endpoint.calls == []
    captured = capsys.readouterr()
    assert API_KEY not in out + err + caplog.text + captured.out + captured.err


def test_d1_tampered_plan_blocked_before_c2(no_dispatch, caplog, capsys):
    forged = dataclasses.replace(plan(), input_text="RAW_D1_CONTENT")
    endpoint = MockEndpoint(payload=payload_for("ready"))
    preview = invoke(product(LIVE), endpoint, plan=forged)
    assert preview["status"] == "BLOCKED_CONFIG"
    assert preview["reason_codes"] == ["INVALID_CONFIGURATION"]
    assert endpoint.calls == []
    assert_safe(preview, caplog, capsys)


@pytest.mark.parametrize("boundary", ["c2", "sdk"])
def test_d1_unexpected_exception_is_safe_and_not_retried(
    boundary, monkeypatch, pipeline, caplog, capsys,
):
    monkeypatch.setitem(os.environ, "OPENAI_API_KEY", API_KEY)
    error = RuntimeError(f"{MARKER} {API_KEY} Authorization: Bearer RAW_D1_CONTENT")
    failure = Mock(side_effect=error)
    if boundary == "c2":
        transport = importlib.import_module("app.responses_web_search.c2_transport")
        monkeypatch.setattr(transport, "request_response", failure)
    else:
        monkeypatch.setattr("openai.resources.responses.Responses.create", failure)
    endpoint = MockEndpoint(payload=payload_for("ready"))
    code, _, out, err = cli(product(CLI), endpoint, argv=("--execute-live",))
    assert code != 0
    assert failure.call_count == 1
    assert endpoint.calls == []
    assert "UNEXPECTED_ERROR" in out + err
    for name in ("c1", "normalize", "parse", "validate"):
        assert getattr(pipeline, name).call_count == 0
    assert pipeline.clients and all(client.is_closed for client in pipeline.clients)
    captured = capsys.readouterr()
    visible = out + err + caplog.text + captured.out + captured.err
    for marker in (MARKER, API_KEY, "Authorization", "Bearer ", "RAW_D1_CONTENT",
                   "Traceback (most recent call last)"):
        assert marker not in visible
