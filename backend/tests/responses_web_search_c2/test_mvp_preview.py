"""MVP diagnostics through the real SDK and existing frozen validation path."""

import importlib
import json
from copy import deepcopy

import httpx2
import pytest
from d1_support import (
    CLI,
    LIVE,
    Terminal,
    cli,
    invoke,
    no_dispatch as blocked_dispatch,
    plan,
)
from openai.resources.responses import Responses
from support import API_KEY, MARKER
from test_sdk_mock_preview_red import payload_for as sdk_payload_for

no_dispatch = blocked_dispatch


def payload_for(case):
    payload = sdk_payload_for(case)
    payload["model"] = plan().config.model
    return payload


@pytest.mark.parametrize(
    "case,status,search,response,citations,candidates",
    [
        ("ready", "PREVIEW_READY", "CONFIRMED", "VALID", "MATCHED", "VALID"),
        ("no-search", "SEARCH_NOT_EXECUTED", "NOT_CONFIRMED",
         "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED"),
        ("discarded", "NO_VALID_CANDIDATES", "CONFIRMED", "VALID",
         "MISMATCH", "INVALID"),
        ("empty", "EMPTY_RESULT", "CONFIRMED", "VALID", "EMPTY", "EMPTY"),
        ("bad-json", "INVALID_OR_INCOMPLETE_RESPONSE", "CONFIRMED", "INVALID",
         "NOT_EVALUATED", "NOT_EVALUATED"),
    ],
)
def test_separate_validation_diagnostics(
    endpoint, case, status, search, response, citations, candidates,
):
    endpoint.payload = payload_for(case)
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    assert len(endpoint.calls) == 1
    assert preview["status"] == status
    assert preview["search_execution"] == search
    assert preview["response_validation"] == response
    assert preview["citation_validation"] == citations
    assert preview["candidate_validation"] == candidates
    if case == "discarded":
        assert preview["issues"] == [
            {"candidate_index": 0, "code": "CITATION_URL_MISMATCH"},
        ]


def test_timeout_never_reports_observed_zero_or_retries(endpoint):
    endpoint.transport_error = httpx2.ReadTimeout
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    assert len(endpoint.calls) == 1
    assert preview["reason_codes"] == ["TIMEOUT"]
    assert preview["search_execution"] == "UNKNOWN"
    assert preview["tool_calls_observed"] is None
    assert preview["citation_validation"] == "NOT_EVALUATED"
    assert preview["candidate_validation"] == "NOT_EVALUATED"


def test_three_candidates_and_partial_validation(endpoint):
    endpoint.payload = payload_for("ready")
    content = endpoint.payload["output"][-1]["content"][0]
    first = json.loads(content["text"])["candidates"][0]
    candidates = [dict(first, topic_draft=f"Candidate {index}",
                       source_url=f"{first['source_url']}/{index}")
                  for index in range(3)]
    content["text"] = json.dumps({"candidates": candidates})
    content["annotations"] = [
        dict(content["annotations"][0], url=item["source_url"])
        for item in candidates
    ]
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    assert len(preview["candidates"]) == 3
    assert preview["candidate_validation"] == "VALID"
    assert preview["citation_validation"] == "MATCHED"

    content["annotations"].pop()
    preview = invoke(module, endpoint)
    assert len(preview["candidates"]) == 2
    assert preview["candidate_validation"] == "PARTIAL"
    assert preview["citation_validation"] == "PARTIAL"

    content["text"] = json.dumps({"candidates": candidates + [candidates[0]]})
    preview = invoke(module, endpoint)
    assert preview["candidates"] == []
    assert preview["reason_codes"] == ["CANDIDATE_LIMIT_EXCEEDED"]
    assert preview["candidate_validation"] == "NOT_EVALUATED"


@pytest.mark.usefixtures("no_dispatch")
def test_readiness_is_offline_and_redacts_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key-never-print")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "synthetic-project-never-print")
    module = importlib.reload(importlib.import_module(CLI))
    stdout, stderr = Terminal(), Terminal()
    code = module.main(["--check-readiness"], stdout=stdout, stderr=stderr)
    report = json.loads(stdout.getvalue())
    assert code == 0
    assert report["api_key_configured"] is True
    assert report["project_configured"] is True
    assert report["model"] == plan().config.model
    assert report["model_access"] == "UNCONFIRMED"
    assert report["project_cost_limits"] == "UNCONFIRMED"
    assert report["paid_call_authorized"] is False
    assert report["dependencies"]["openai"] == "3.50.0"
    assert "synthetic-" not in stdout.getvalue() + stderr.getvalue()


@pytest.mark.usefixtures("no_dispatch")
def test_readiness_missing_key_requires_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    module = importlib.reload(importlib.import_module(CLI))
    stdout = Terminal()
    assert module.main(["--check-readiness"], stdout=stdout) == 0
    report = json.loads(stdout.getvalue())
    assert report["api_key_configured"] is False
    assert report["status"] == "READINESS_INCOMPLETE"


@pytest.mark.parametrize("timeout,outgoing_limit", [(False, 1), (True, 1), (False, 2)])
def test_request_limit_observes_serialized_body_only(
    endpoint, timeout, outgoing_limit, monkeypatch, caplog, capsys,
):
    caplog.set_level("DEBUG")
    endpoint.payload = payload_for("bad-json")
    if timeout:
        endpoint.transport_error = httpx2.ReadTimeout
    original_create = Responses.create

    def create_with_observed_limit(resource, *args, **kwargs):
        # Test-only mutation proves observation reads the serialized request.
        kwargs["max_tool_calls"] = outgoing_limit
        return original_create(resource, *args, **kwargs)

    monkeypatch.setattr(Responses, "create", create_with_observed_limit)
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    assert len(endpoint.calls) == 1
    assert preview["request_max_tool_calls"] == json.loads(
        endpoint.calls[0].content,
    )["max_tool_calls"] == outgoing_limit
    assert preview["candidates"] == []
    captured = capsys.readouterr()
    visible = json.dumps(preview) + caplog.text + captured.out + captured.err
    for private_value in (API_KEY, MARKER, plan().input_text,
                          "independent query", "https://example.com",
                          "not candidate JSON"):
        assert private_value not in visible


@pytest.mark.parametrize("case", [
    "second-completed", "second-failed", "second-open-page", "third-call",
    "response-incomplete", "message-incomplete", "refusal", "bad-json",
    "citation-mismatch", "oversized-text", "oversized-annotations",
    "oversized-output", "candidate-limit", "duplicate", "unsafe-url",
])
def test_d2_partial_boundaries(case, endpoint):
    payload = payload_for("ready")
    call = payload["output"][0]
    pending = deepcopy(call)
    pending.update(id="ws_pending", status="searching")
    payload["output"].insert(1, pending)
    message = payload["output"][-1]
    part = message["content"][0]
    if case == "second-completed":
        pending["status"] = "completed"
    elif case == "second-failed":
        pending["status"] = "failed"
    elif case == "second-open-page":
        pending["action"]["type"] = "open_page"
    elif case == "third-call":
        payload["output"].insert(0, deepcopy(call))
    elif case == "response-incomplete":
        payload["status"] = "incomplete"
    elif case == "message-incomplete":
        message["status"] = "incomplete"
    elif case == "refusal":
        message["content"] = [{"type": "refusal", "refusal": "private"}]
    elif case == "bad-json":
        part["text"] = "invalid json"
    elif case == "citation-mismatch":
        part["annotations"][0]["url"] += "/other"
    elif case == "oversized-text":
        part["text"] = "x" * 32769
    elif case == "oversized-annotations":
        part["annotations"] *= 33
    elif case == "oversized-output":
        payload["output"].extend(
            {"type": "reasoning", "id": "rs_extra", "summary": []}
            for _ in range(17 - len(payload["output"]))
        )
    else:
        candidates = json.loads(part["text"])["candidates"]
        if case == "candidate-limit":
            candidates *= 4
        elif case == "duplicate":
            candidates *= 2
        else:
            candidates[0]["source_url"] = "http://localhost/private"
        part["text"] = json.dumps({"candidates": candidates})
    original = deepcopy(payload)
    endpoint.payload = payload
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    assert endpoint.payload == original
    assert len(endpoint.calls) == 1
    if case == "duplicate":
        assert preview["status"] == "PARTIAL_PREVIEW_READY"
        assert len(preview["candidates"]) == 1
        assert preview["issues"] == [{"candidate_index": 1,
                                      "code": "DUPLICATE_CANDIDATE"}]
    else:
        assert preview["status"] not in {"PARTIAL_PREVIEW_READY", "PREVIEW_READY"}
        assert preview["candidates"] == []


def test_d2_cli_and_request_limit_boundary(endpoint, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    payload = payload_for("ready")
    pending = deepcopy(payload["output"][0])
    pending.update(id="ws_pending", status="searching")
    payload["output"].insert(1, pending)
    endpoint.payload = payload
    module = importlib.reload(importlib.import_module(CLI))
    code, _, stdout, _ = cli(module, endpoint, argv=["--execute-live"])
    assert code == 0
    preview = json.loads(stdout)
    assert preview["status"] == "PARTIAL_PREVIEW_READY"
    assert preview["response_validation"] == "PARTIAL"
    assert preview["review_status"] == "REVIEW_REQUIRED"
    assert preview["publication_status"] == "NOT_FOR_PUBLICATION"
    assert preview["independent_source_verified"] is False
    assert preview["publish_authorization"] == "NONE"
    assert len(endpoint.calls) == 1
    from app.responses_web_search.live_compatibility import parse_d2_response
    from app.responses_web_search.types import SearchRunConfig

    for request_limit in (2, None):
        assert parse_d2_response(
            payload, SearchRunConfig(), request_max_tool_calls=request_limit,
        ) is None


@pytest.mark.parametrize(
    "case,citation_count,direct_count,source_count",
    [
        ("no-citations", 0, 0, 1),
        ("mismatch", 1, 0, 1),
        ("exact", 1, 1, 1),
        ("repeated-citation", 2, 1, 1),
        ("source-missing", 0, 0, None),
        ("url-query-differs", 1, 0, 0),
    ],
)
def test_d2_citation_aggregate_diagnostics(
    case, citation_count, direct_count, source_count, endpoint, caplog, capsys,
):
    caplog.set_level("DEBUG")
    payload = payload_for("ready")
    part = payload["output"][-1]["content"][0]
    candidate = json.loads(part["text"])["candidates"][0]
    url = candidate["source_url"]
    call = payload["output"][0]
    call["action"]["sources"] = [{"type": "url", "url": url}]
    if case in {"no-citations", "source-missing"}:
        part["annotations"] = []
    elif case == "mismatch":
        part["annotations"][0]["url"] += "/other"
    elif case == "url-query-differs":
        candidate["source_url"] += "?query=private"
        part["text"] = json.dumps({"candidates": [candidate]})
    elif case == "repeated-citation":
        part["annotations"] *= 2
    if case == "source-missing":
        call["action"].pop("sources")
    pending = deepcopy(call)
    pending.update(id="ws_pending", status="searching")
    payload["output"].insert(1, pending)
    original = deepcopy(payload)
    endpoint.payload = payload
    module = importlib.reload(importlib.import_module(LIVE))
    preview = invoke(module, endpoint)
    counts = preview["citation_diagnostics"]
    assert counts == {
        "candidate_count": 1, "url_citation_count": citation_count,
        "direct_matched_candidate_count": direct_count,
        "action_sources_matched_candidate_count": source_count,
    }
    assert preview["status"] == (
        "PARTIAL_PREVIEW_READY" if direct_count else "NO_VALID_CANDIDATES"
    )
    assert preview["citation_validation"] == ("MATCHED" if direct_count else "MISMATCH")
    assert len(preview["candidates"]) == direct_count
    assert endpoint.payload == original
    assert len(endpoint.calls) == 1
    captured = capsys.readouterr()
    visible = json.dumps(counts) + caplog.text + captured.out + captured.err
    for private_value in (url, API_KEY, MARKER, plan().input_text,
                          "independent query", "query=private", part["text"]):
        assert private_value not in visible
