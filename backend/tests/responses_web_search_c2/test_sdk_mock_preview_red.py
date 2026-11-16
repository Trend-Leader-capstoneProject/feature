"""INT-01..08: SDK Mock connection contract, with no Green substitute.

Run with --confcutdir=tests/responses_web_search_c2. Existing C2 guards block
real network, secrets and operational imports. Controls exercise real SDK/C1/
S1/S0 directly, never construct a Preview. Product imports are deferred until
each contract test, after spies are installed (including cached alias reloads).
"""

import importlib
import json
import sys
import traceback
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
import pytest
from openai.types.responses import Response
from support import (
    API_KEY,
    INPUT,
    MARKER,
    MODEL,
    TIMEOUT,
    MockEndpoint,
    assert_request,
    original_response,
)

from app.responses_web_search.types import SearchRunConfig

URL = "https://vendor.example.test/releases/sdk-mock"
CANDIDATE = {
    "topic_draft": "SDK Mock 연결 검토 후보",
    "source_url": URL,
    "source_title_reference": "원래 제목 — 내부 검토용",
}
MODULE = "app.responses_web_search.sdk_mock_preview"


def payload_for(case):
    """Only replace C2's deliberately invalid text and its empty citations."""
    payload = original_response()
    content = payload["output"][-1]["content"][0]
    content["text"] = json.dumps({"candidates": [CANDIDATE]}, ensure_ascii=False)
    content["annotations"] = [{
        "type": "url_citation", "url": URL,
        "title": CANDIDATE["source_title_reference"],
        "start_index": 0, "end_index": 1,
    }]
    if case == "rejected":
        # Existing Frozen B-03: an explicit null must survive C1 and be refused.
        payload["output"][1]["status"] = None
    elif case == "discarded":
        content["annotations"][0]["url"] = "https://vendor.example.test/other"
    elif case == "no-search":
        payload["output"].pop(0)
    elif case == "empty":
        content["text"] = '{"candidates":[]}'
    elif case == "bad-json":
        content["text"] = "not candidate JSON"
    return payload


@pytest.fixture
def pipeline(monkeypatch):
    """Observe real public functions; do not fabricate downstream results."""
    events = Mock()
    results = {}
    spies = SimpleNamespace(events=events, results=results, clients=[])
    for name, module_name, function in (
        ("c2", "c2_transport", "request_response"),
        ("c1", "c1_adapter", "convert_response"),
        ("normalize", "normalizer", "normalize_response"),
        ("parse", "parser", "parse_response"),
        ("validate", "validator", "validate_candidates"),
    ):
        module = importlib.import_module(f"app.responses_web_search.{module_name}")

        def observe(*args, _impl=getattr(module, function), _name=name, **kwargs):
            result = _impl(*args, **kwargs)
            results.setdefault(_name, []).append(result)
            return result

        spy = Mock(wraps=observe)
        monkeypatch.setattr(module, function, spy)
        setattr(spies, name, spy)
        events.attach_mock(spy, name)

    # Reusing either existing orchestrator is outside this Slice's contract.
    for module_name, function in (
        ("s1_service", "run_synthetic_preview"), ("service", "run_preview"),
    ):
        module = importlib.import_module(f"app.responses_web_search.{module_name}")
        monkeypatch.setattr(module, function, Mock(side_effect=AssertionError(
            "Existing Preview orchestrator must not be used",
        )))

    original_init = httpx2.Client.__init__

    def track_client(client, *args, **kwargs):
        original_init(client, *args, **kwargs)
        spies.clients.append(client)

    monkeypatch.setattr(httpx2.Client, "__init__", track_client)
    return spies


def preview_module():
    # Never catch ModuleNotFoundError, skip, xfail or provide a fallback.
    return (
        importlib.reload(sys.modules[MODULE]) if MODULE in sys.modules
        else importlib.import_module(MODULE)
    )


def invoke(module, endpoint, **overrides):
    args = dict(
        api_key=API_KEY, model=MODEL, input_text=INPUT, timeout=TIMEOUT,
        config=SearchRunConfig(), mock_transport=httpx2.MockTransport(endpoint.handle),
    )
    args.update(overrides)
    return module.run_sdk_mock_preview(**args)


def assert_safe(preview, caplog, capsys):
    assert json.loads(json.dumps(preview, allow_nan=False)) == preview
    assert preview["mode"] == "SDK_MOCK"
    assert preview["request_started_at_utc"] is None
    assert preview["response_received_at_utc"] is None
    for value in (preview, *preview["candidates"]):
        assert value["review_status"] == "REVIEW_REQUIRED"
        assert value["publication_status"] == "NOT_FOR_PUBLICATION"
        assert value["publish_authorization"] == "NONE"
        assert value["independent_source_verified"] is False
        # No fabricated observations, real search time, cost or ranking.
        for key in (
            "searched_at_utc", "observed_at_utc", "cost", "actual_cost",
            "rank", "ranking", "usage", "search_cost", "total_cost",
        ):
            assert value.get(key) is None
    for candidate in preview["candidates"]:
        assert candidate["source_published_at"] is None
        assert candidate["proposed_category_ref"] == "IT_DIGITAL"
    captured = capsys.readouterr()
    visible = "\n".join((repr(preview), caplog.text, captured.out, captured.err))
    for secret in (API_KEY, MARKER, "Bearer "):
        assert secret not in visible


def assert_result(preview, *, status, search, validation, calls, reasons=(), issues=()):
    assert preview["status"] == status
    assert preview["search_execution"] == search
    assert preview["response_validation"] == validation
    assert preview["tool_calls_observed"] == calls
    if calls is not None:
        assert type(preview["tool_calls_observed"]) is int
    assert preview["reason_codes"] == list(reasons)
    assert preview["issues"] == list(issues)
    if status != "PREVIEW_READY":
        assert preview["candidates"] == []


def assert_flow(pipeline, expected):
    assert [call[0] for call in pipeline.events.mock_calls] == expected
    for name in ("c2", "c1", "normalize", "parse", "validate"):
        assert getattr(pipeline, name).call_count == expected.count(name)
    if "c1" in expected:
        response, = pipeline.results["c2"]
        assert isinstance(response, Response)
        assert pipeline.c1.call_args.args[0] is response
    if "normalize" in expected:
        converted, = pipeline.results["c1"]
        assert pipeline.normalize.call_args.args[0] is converted
    if "parse" in expected:
        normalized, = pipeline.results["normalize"]
        assert pipeline.parse.call_args.args[0] is normalized.parser_input
    if "validate" in expected:
        parsed, = pipeline.results["parse"]
        assert pipeline.validate.call_args.args[0] is parsed


def assert_closed(pipeline, count=1):
    assert len(pipeline.clients) == count
    assert len({id(client) for client in pipeline.clients}) == count
    assert all(client.is_closed for client in pipeline.clients)


@pytest.mark.parametrize("case", [
    "ready", "rejected", "discarded", "no-search", "empty", "bad-json",
])
def test_fixture_sdk_pipeline_control(case, endpoint, http_client, sdk_responses):
    """Independent fixture control; missing Preview cannot mask SDK/Mock errors."""
    from app.responses_web_search.c1_adapter import convert_response
    from app.responses_web_search.c2_transport import request_response
    from app.responses_web_search.normalizer import normalize_response
    from app.responses_web_search.parser import parse_response
    from app.responses_web_search.validator import validate_candidates

    endpoint.payload = payload_for(case)
    original = deepcopy(endpoint.payload)
    response = request_response(
        api_key=API_KEY, model=MODEL, input_text=INPUT,
        timeout=TIMEOUT, http_client=http_client,
    )
    assert sdk_responses == [response]
    converted = convert_response(response)
    assert converted["output"] == original["output"]
    normalized = normalize_response(converted, SearchRunConfig())
    if case == "rejected":
        assert normalized.outcome == "REJECTED"
        assert normalized.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
    else:
        assert normalized.outcome == "NORMALIZED"
        parsed = parse_response(normalized.parser_input, SearchRunConfig())
        if case in {"no-search", "bad-json"}:
            assert parsed.status == (
                "SEARCH_NOT_EXECUTED" if case == "no-search"
                else "INVALID_OR_INCOMPLETE_RESPONSE"
            )
        else:
            assert parsed.status is None
            candidates, issues = validate_candidates(parsed)
            assert len(candidates) == (1 if case == "ready" else 0)
            assert [(item.candidate_index, item.code) for item in issues] == (
                [(0, "CITATION_URL_MISMATCH")] if case == "discarded" else []
            )
    assert endpoint.payload == original
    assert_request(endpoint)
    assert http_client.is_closed


def test_c1_failure_injection_control(
    endpoint, http_client, sdk_responses, monkeypatch, caplog, capsys,
):
    """Prove the injected fault reaches real C1 after successful SDK receipt."""
    from app.responses_web_search.c1_adapter import C1ConversionError, convert_response
    from app.responses_web_search.c2_transport import request_response

    endpoint.payload = payload_for("ready")
    response = request_response(
        api_key=API_KEY, model=MODEL, input_text=INPUT,
        timeout=TIMEOUT, http_client=http_client,
    )
    assert sdk_responses == [response]
    monkeypatch.setattr(Response, "to_dict", Mock(side_effect=ValueError(MARKER)))
    with pytest.raises(C1ConversionError) as caught:
        convert_response(response)
    captured = capsys.readouterr()
    visible = "\n".join((
        str(caught.value), repr(caught.value),
        "".join(traceback.format_exception(caught.value)),
        caplog.text, captured.out, captured.err,
    ))
    for secret in (API_KEY, MARKER, "Bearer "):
        assert secret not in visible
    assert_request(endpoint)
    assert http_client.is_closed


@pytest.mark.parametrize("case", [
    "ready", "rejected", "discarded", "no-search", "empty", "bad-json",
])
def test_int01_04_05_06_07_sdk_to_preview(
    case, pipeline, sdk_responses, caplog, capsys,
):
    module = preview_module()
    endpoint = MockEndpoint(payload=payload_for(case))
    original = deepcopy(endpoint.payload)
    preview = invoke(module, endpoint)
    assert_request(endpoint)
    assert len(sdk_responses) == 1
    assert sdk_responses[0] is pipeline.results["c2"][0]
    assert pipeline.results["c1"][0]["output"] == original["output"]
    expected = ["c2", "c1", "normalize"]
    if case != "rejected":
        expected.append("parse")
    if case in {"ready", "discarded", "empty"}:
        expected.append("validate")
    assert_flow(pipeline, expected)
    assert endpoint.payload == original
    assert_result(
        preview,
        status={
            "ready": "PREVIEW_READY", "rejected": "INVALID_OR_INCOMPLETE_RESPONSE",
            "discarded": "NO_VALID_CANDIDATES", "no-search": "SEARCH_NOT_EXECUTED",
            "empty": "EMPTY_RESULT", "bad-json": "INVALID_OR_INCOMPLETE_RESPONSE",
        }[case],
        search="NOT_CONFIRMED" if case == "no-search" else "CONFIRMED",
        validation=(
            "NOT_EVALUATED" if case == "no-search"
            else "INVALID" if case in {"rejected", "bad-json"} else "VALID"
        ),
        calls=0 if case == "no-search" else 1,
        reasons=("RESPONSE_STRUCTURE_INVALID",)
        if case in {"rejected", "bad-json"} else (),
        issues=({"candidate_index": 0, "code": "CITATION_URL_MISMATCH"},)
        if case == "discarded" else (),
    )
    if case == "ready":
        candidate, = preview["candidates"]
        for key, value in CANDIDATE.items():
            assert candidate[key] == value
    if case == "rejected":
        normalized, = pipeline.results["normalize"]
        assert normalized.outcome == "REJECTED"
        assert list(normalized.reason_codes) == preview["reason_codes"]
    assert_safe(preview, caplog, capsys)
    assert_closed(pipeline)


def test_int02_07_08_c2_failure_stops_pipeline(pipeline, caplog, capsys):
    module = preview_module()
    endpoint = MockEndpoint(status=429)
    preview = invoke(module, endpoint)
    assert_request(endpoint)  # Retry-sensitive: retry-after=0/x-should-retry=true.
    assert_flow(pipeline, ["c2"])
    assert_result(
        preview, status="UPSTREAM_ERROR", search="UNKNOWN",
        validation="NOT_EVALUATED", calls=None, reasons=("RATE_LIMITED",),
    )
    assert_safe(preview, caplog, capsys)
    assert_closed(pipeline)


def test_int03_07_c1_failure_after_real_sdk(
    pipeline, sdk_responses, monkeypatch, caplog, capsys,
):
    module = preview_module()
    endpoint = MockEndpoint(payload=payload_for("ready"))
    monkeypatch.setattr(Response, "to_dict", Mock(side_effect=ValueError(MARKER)))
    preview = invoke(module, endpoint)
    assert_request(endpoint)
    assert len(sdk_responses) == 1
    assert_flow(pipeline, ["c2", "c1"])
    assert sdk_responses[0] is pipeline.results["c2"][0]
    assert_result(
        preview, status="INVALID_OR_INCOMPLETE_RESPONSE", search="UNKNOWN",
        validation="NOT_EVALUATED", calls=None, reasons=("C1_CONVERSION_FAILED",),
    )
    assert_safe(preview, caplog, capsys)
    assert_closed(pipeline)


def test_int07_08_config_error_closes_client_before_sdk(
    pipeline, sdk_responses, caplog, capsys,
):
    module = preview_module()
    endpoint = MockEndpoint()
    preview = invoke(module, endpoint, model="")
    assert endpoint.calls == []
    assert sdk_responses == []
    assert_flow(pipeline, ["c2"])
    assert_result(
        preview, status="BLOCKED_CONFIG", search="UNKNOWN",
        validation="NOT_EVALUATED", calls=None, reasons=("INVALID_CONFIGURATION",),
    )
    assert_safe(preview, caplog, capsys)
    assert_closed(pipeline)


def test_int08_independent_clients_per_invocation(pipeline, caplog, capsys):
    module = preview_module()
    for _ in range(2):
        endpoint = MockEndpoint(payload=payload_for("ready"))
        preview = invoke(module, endpoint)
        assert preview["status"] == "PREVIEW_READY"
        assert_request(endpoint)
        assert_safe(preview, caplog, capsys)
        assert pipeline.clients[-1].is_closed
    assert_closed(pipeline, count=2)


@pytest.mark.parametrize("kind", ["none", "arbitrary", "http-client"])
def test_int07_08_non_mock_transport_rejected(
    kind, pipeline, caplog, capsys,
):
    module = preview_module()
    endpoint = MockEndpoint()
    # A client backed by MockTransport is still not the allowed transport input.
    with httpx2.Client(
        transport=httpx2.MockTransport(endpoint.handle), trust_env=False,
    ) as supplied_client:
        invalid = {
            "none": None, "arbitrary": object(), "http-client": supplied_client,
        }[kind]
        preview = invoke(module, endpoint, mock_transport=invalid)
    assert endpoint.calls == []
    assert_flow(pipeline, [])
    assert_result(
        preview, status="BLOCKED_CONFIG", search="UNKNOWN",
        validation="NOT_EVALUATED", calls=None, reasons=("INVALID_CONFIGURATION",),
    )
    assert_safe(preview, caplog, capsys)
    assert all(client.is_closed for client in pipeline.clients)
