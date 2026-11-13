"""Offline premises pass independently; converter contracts intentionally stay Red.

No converter fallback, xfail, Preview, or operational orchestration is provided.
"""

import importlib
import json
import os
import socket
import subprocess
import traceback
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path

import httpx2
import pytest
from openai import OpenAI
from openai.types.responses import Response
from pydantic_core import PydanticSerializationError

from app.responses_web_search.normalizer import normalize_response
from app.responses_web_search.parser import parse_response
from app.responses_web_search.types import SearchRunConfig
from app.responses_web_search.validator import validate_candidates

OPTIONS = dict(
    mode="json", use_api_names=True, exclude_unset=True,
    exclude_defaults=False, exclude_none=False,
)
CANDIDATE = {
    "topic_draft": "Offline SDK evidence",
    "source_url": "https://example.com/news/c1?ref=original#citation",
    "source_title_reference": "Synthetic source",
}
MARKER = "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"


def original_response(variant="normal"):
    """Independent HTTP JSON, never derived from SDK serialization or S1 F-BASE."""
    text = json.dumps({"candidates": [CANDIDATE]}, ensure_ascii=False)
    output = [{
        "id": "ws_c1_1", "type": "web_search_call", "status": "completed",
        "action": {"type": "search", "query": "offline synthetic query"},
    }, {
        "id": "msg_c1", "type": "message", "role": "assistant",
        "status": "completed", "phase": "final_answer",
        "content": [{
            "type": "output_text", "text": text,
            "annotations": [{
                "type": "url_citation", "url": CANDIDATE["source_url"],
                "title": "Original citation title", "start_index": 7,
                "end_index": 29,
            }],
        }],
    }]
    if variant in {"omitted", "null", "completed"}:
        reasoning = {"id": "rs_c1", "type": "reasoning", "summary": []}
        if variant != "omitted":
            reasoning["status"] = None if variant == "null" else "completed"
        output.insert(0, reasoning)
    if variant == "two_searches":
        second = deepcopy(output[0])
        second["id"] = "ws_c1_2"
        second["action"]["query"] = "second independent query"
        output.insert(1, second)
    return {
        "id": "resp_c1", "object": "response", "created_at": 1794528000,
        "model": "offline-test-model", "status": "completed", "output": output,
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
    }


def receive(original):
    """Exercise the SDK's default HTTP response construction, not model_validate."""
    calls = []
    before = deepcopy(original)

    def handle(request):
        calls.append((request.method, str(request.url)))
        assert request.headers["authorization"] == "Bearer test-only-key"
        assert json.loads(request.content)["input"] == "offline fixture only"
        return httpx2.Response(200, json=original)

    with httpx2.Client(
        transport=httpx2.MockTransport(handle), trust_env=False,
    ) as http_client:
        with OpenAI(
            api_key="test-only-key", organization="test-org", project="test-project",
            webhook_secret="test-only-secret", base_url="https://c1.invalid/v1",
            max_retries=0, http_client=http_client,
        ) as client:
            response = client.responses.create(
                model="offline-test-model", input="offline fixture only",
            )
    assert calls == [("POST", "https://c1.invalid/v1/responses")]
    assert original == before
    assert isinstance(response, Response)
    return response


def assert_evidence(converted, original):
    assert type(converted) is dict
    assert json.loads(json.dumps(converted, allow_nan=False)) == converted
    assert converted["status"] == original["status"]
    # Complete evidence items: count, order, action/status, phase, exact text,
    # annotation order/URL/title/offset, and absent versus explicit null fields.
    assert converted["output"] == original["output"]


def assert_pipeline(converted, variant):
    config = SearchRunConfig()
    normalized = normalize_response(converted, config)
    if variant in {"null", "two_searches"}:
        assert normalized.outcome == "REJECTED"
        assert normalized.parser_input is None
        assert normalized.reason_codes == (
            "TOOL_CALL_LIMIT_EXCEEDED" if variant == "two_searches"
            else "RESPONSE_STRUCTURE_INVALID",
        )
        if variant == "two_searches":
            assert normalized.execution_evidence.web_search_calls_observed == 2
        return
    assert normalized.outcome == "NORMALIZED"
    parsed = parse_response(normalized.parser_input, config)
    assert parsed.status is None
    accepted, issues = validate_candidates(parsed)
    assert issues == ()
    assert len(accepted) == 1
    candidate = accepted[0]
    assert candidate.topic_draft == CANDIDATE["topic_draft"]
    assert candidate.source_url == CANDIDATE["source_url"]
    assert candidate.source_title_reference == CANDIDATE["source_title_reference"]


def converter_module():
    # Deliberately loaded inside tests, after SDK/fixture premises are established.
    return importlib.import_module("app.responses_web_search.c1_adapter")


def test_isolation_guards(isolated_io):
    """GC1-12: bounded self-probes stop before DNS/socket/file/env side effects."""
    probes = [
        lambda: socket.getaddrinfo("c1.invalid", 443),
        lambda: socket.create_connection(("c1.invalid", 443)),
        lambda: Path(".env.c1-guard-probe").read_text(),
        lambda: os.environ["OPENAI_API_KEY"],
        lambda: importlib.import_module("app.db.c1_guard_probe"),
    ]
    for probe in probes:
        with pytest.raises(AssertionError, match="C1 .* forbidden"):
            probe()
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="C1 external effect forbidden"):
            sock.connect(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="C1 external effect forbidden"):
        subprocess.Popen(["c1-never-executed"])
    # Import guard has its own assertion; six I/O probes reached blocked().
    isolated_io.extend(["blocked"] * 6)


@pytest.mark.parametrize("variant", [
    "normal", "omitted", "null", "completed", "two_searches",
])
def test_sdk_fixture_control(variant):
    """Premise only, NOT C1 PASS: GC1-01/13 and serialization candidate behavior."""
    assert version("openai") == "3.50.0"
    assert version("httpx2") == "2.16.0"
    original = original_response(variant)
    response = receive(original)
    before = deepcopy(response)
    serialized = response.to_dict(**OPTIONS)
    assert_evidence(serialized, original)
    assert response == before
    assert_pipeline(serialized, variant)


def test_r01_receive_convert_and_existing_pipeline():
    """GC1-02/03/04/07/10/11/13/14; GC1-01 checked by SDK control."""
    original = original_response()
    response = receive(original)
    before = deepcopy(response)
    converted = converter_module().convert_response(response)
    assert_evidence(converted, original)
    assert response == before
    assert_pipeline(converted, "normal")


@pytest.mark.parametrize("variant", ["omitted", "null", "completed"])
def test_r02_reasoning_status_preservation(variant):
    """GC1-05/06/11/14: missing and explicit null must remain distinct."""
    original = original_response(variant)
    response = receive(original)
    converted = converter_module().convert_response(response)
    assert_evidence(converted, original)
    reasoning = converted["output"][0]
    if variant == "omitted":
        assert "status" not in reasoning
    elif variant == "null":
        assert "status" in reasoning and reasoning["status"] is None
    else:
        assert reasoning["status"] == "completed"
    assert_pipeline(converted, variant)


def test_r03_preserve_two_search_calls_and_reject_limit():
    """GC1-03/08/11/14: preserve both searches before S1 rejects them."""
    original = original_response("two_searches")
    response = receive(original)
    converted = converter_module().convert_response(response)
    assert_evidence(converted, original)
    assert sum(item["type"] == "web_search_call" for item in converted["output"]) == 2
    assert_pipeline(converted, "two_searches")


def assert_safe_failure(module, value):
    with pytest.raises(module.C1ConversionError) as captured:
        module.convert_response(value)
    assert str(captured.value) == "C1 response conversion failed"
    assert MARKER not in repr(captured.value)
    assert MARKER not in "".join(traceback.format_exception(captured.value))


def test_r04_wrong_input_is_a_bounded_failure():
    """GC1-09: a dict is not an SDK Response; never return a success-shaped dict."""
    module = converter_module()
    assert_safe_failure(module, {"body": MARKER})


def test_r04_real_serialization_failure_is_bounded():
    """GC1-09: reproduce an actual serializer error without a fake converter."""
    response = receive(original_response())

    # SDK models allow extras; an unsupported value fails mode='json' serialization.
    unsupported = type(MARKER, (), {})()
    response.opaque_c1_marker = unsupported
    with pytest.raises(PydanticSerializationError) as raw_error:
        response.to_dict(**OPTIONS)
    assert MARKER in str(raw_error.value), "Premise: raw SDK error contains marker"
    module = converter_module()
    assert_safe_failure(module, response)
