"""Gate B Red Phase 1: frozen v0.2.2 sections 2.3/2.4/5.P/6.

Internal test binding (not a public API or SDK contract):
app.responses_web_search.s1_service.run_synthetic_preview(*, config, adapter)
returns the JSON-compatible Preview dict. The injected in-memory Mock exposes
read() -> whole synthetic response, or raises builtin TimeoutError. No new
Adapter/SDK type is required. Import is deferred so absent orchestration is a
runtime Red, never a collection error; transitive import errors are not hidden.

Ownership: S1 coordinates one Mock read -> real Normalizer -> real S0 Parser
-> real S0 Validator -> Preview. Helpers below observe calls and assert output;
they never implement a substitute Preview or call the S0 FIXTURE_ONLY service.
Spies are installed before importing/reloading S1 so function aliases remain
bound to the current test's spies, independently of test execution order.

P-02 maps E-01's timeout/no-application-retry/no-downstream-call assertions to
the same test, rather than duplicating the identical input/execution. This is
not E-02, SDK retries (E-08/Gate C), or complete E/security/log coverage.
The four passing fixture controls establish real Gate A/S0 preconditions only.
P-03 Preview is out of scope: its observable zero evidence control below guards
against confusing zero with P-02/P-08 null, without claiming P-03 coverage.

Gate C/D, G5/G6 HOLD and P4 NOT FROZEN are unchanged. No SDK, real API,
DB/Redis/publishing/file persistence is allowed by the existing S1 guards.
"""

import copy
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from .fixtures import URL, content, response


def payload_for(ac):
    payload = response()
    if ac == "P-05":
        content(payload)["text"] = '{"candidates":[]}'
    elif ac == "P-07":
        content(payload)["annotations"][0]["url"] = (
            "https://vendor.example.test/releases/other"
        )
    elif ac == "P-08":
        payload["output"] = {"broken": "not an output list"}
    return payload


def assert_safety(value):
    assert value["review_status"] == "REVIEW_REQUIRED"
    assert value["publication_status"] == "NOT_FOR_PUBLICATION"
    assert value["publish_authorization"] == "NONE"
    assert value["independent_source_verified"] is False


def assert_preview(preview, *, status, search, validation, calls):
    assert isinstance(preview, dict)
    # Enforce JSON compatibility without writing a file.
    assert json.loads(json.dumps(preview, allow_nan=False)) == preview
    assert preview["mode"] == "S1_SYNTHETIC"
    assert preview["status"] == status
    assert preview["search_execution"] == search
    assert preview["response_validation"] == validation
    if calls is None:
        assert preview["tool_calls_observed"] is None
    else:
        assert type(preview["tool_calls_observed"]) is int
        assert preview["tool_calls_observed"] == calls
    assert preview["request_started_at_utc"] is None
    assert preview["response_received_at_utc"] is None
    assert_safety(preview)
    assert isinstance(preview["reason_codes"], list)
    assert all(isinstance(code, str) and code for code in preview["reason_codes"])
    assert isinstance(preview["issues"], list)
    assert isinstance(preview["candidates"], list)
    assert "simulated_web_search_executed" not in preview
    assert "candidate_count" not in preview
    for candidate in preview["candidates"]:
        assert_safety(candidate)
        assert candidate["source_published_at"] is None
        assert candidate["proposed_category_ref"] == "IT_DIGITAL"


@pytest.fixture
def pipeline(monkeypatch, isolated_session):
    normalizer = importlib.import_module("app.responses_web_search.normalizer")
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    service = importlib.import_module("app.responses_web_search.service")
    types = importlib.import_module("app.responses_web_search.types")
    spies = SimpleNamespace(
        normalize=Mock(wraps=normalizer.normalize_response),
        parse=Mock(wraps=parser.parse_response),
        validate=Mock(wraps=validator.validate_candidates),
        fixture_service=Mock(side_effect=AssertionError("S0 service is forbidden")),
        config=types.SearchRunConfig(),
        events=Mock(),
    )
    monkeypatch.setattr(normalizer, "normalize_response", spies.normalize)
    monkeypatch.setattr(parser, "parse_response", spies.parse)
    monkeypatch.setattr(validator, "validate_candidates", spies.validate)
    monkeypatch.setattr(service, "run_preview", spies.fixture_service)
    for name in ("normalize", "parse", "validate"):
        spies.events.attach_mock(getattr(spies, name), name)
    return spies


def run_s1(pipeline, *, payload=None, error=None):
    original = copy.deepcopy(payload)
    adapter = Mock(spec_set=["read"])
    adapter.read.return_value = payload
    adapter.read.side_effect = error
    pipeline.events.attach_mock(adapter.read, "read")
    # Deliberately absent in Red Phase 1. Do not catch/xfail/importorskip.
    name = "app.responses_web_search.s1_service"
    module = (
        importlib.reload(sys.modules[name]) if name in sys.modules
        else importlib.import_module(name)
    )
    preview = module.run_synthetic_preview(config=pipeline.config, adapter=adapter)
    adapter.read.assert_called_once_with()
    pipeline.fixture_service.assert_not_called()
    assert payload == original
    return preview


def assert_flow(pipeline, payload, *, normalized):
    pipeline.normalize.assert_called_once_with(payload, pipeline.config)
    if not normalized:
        pipeline.parse.assert_not_called()
        pipeline.validate.assert_not_called()
        assert [event[0] for event in pipeline.events.mock_calls] == [
            "read", "normalize",
        ]
        return
    projected = pipeline.parse.call_args.args[0]
    pipeline.parse.assert_called_once_with(projected, pipeline.config)
    # Selected responses project unchanged; no test-side normalization replica.
    assert projected == payload
    pipeline.validate.assert_called_once()
    parsed_input = pipeline.validate.call_args.args[0]
    assert parsed_input.status is None
    assert parsed_input.tool_calls_observed == 1
    assert [event[0] for event in pipeline.events.mock_calls] == [
        "read", "normalize", "parse", "validate",
    ]


@pytest.mark.parametrize("ac", ["P-01", "P-05", "P-07", "P-08"])
def test_fixture_preconditions_do_not_depend_on_preview(ac, isolated_session):
    payload = payload_for(ac)
    original = copy.deepcopy(payload)
    normalizer = importlib.import_module("app.responses_web_search.normalizer")
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    config = importlib.import_module("app.responses_web_search.types").SearchRunConfig()
    result = normalizer.normalize_response(payload, config)
    assert payload == original
    if ac == "P-08":
        assert result.outcome == "REJECTED"
        assert result.parser_input is None
        assert result.execution_evidence.web_search_calls_observed is None
        assert result.execution_evidence.completed_search_actions is None
        assert result.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
        # A genuinely observed zero must remain distinct from broken output.
        zero = response()
        zero["output"].pop(0)
        evidence = normalizer.normalize_response(zero, config).execution_evidence
        assert type(evidence.web_search_calls_observed) is int
        assert evidence.web_search_calls_observed == 0
        return
    assert result.outcome == "NORMALIZED"
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    parsed = parser.parse_response(result.parser_input, config)
    assert parsed.status is None
    accepted, issues = validator.validate_candidates(parsed)
    assert len(parsed.candidates) == (0 if ac == "P-05" else 1)
    assert len(accepted) == (1 if ac == "P-01" else 0)
    assert [(issue.candidate_index, issue.code) for issue in issues] == (
        [(0, "CITATION_URL_MISMATCH")] if ac == "P-07" else []
    )


def test_p01_base_is_ready_but_never_authorized(pipeline):
    payload = payload_for("P-01")
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["reason_codes"] == []
    assert preview["issues"] == []
    assert len(preview["candidates"]) == 1
    candidate = preview["candidates"][0]
    assert candidate["topic_draft"] == "가상 기기 출시"
    assert candidate["source_url"] == URL
    assert candidate["source_title_reference"] == "가상 공식 발표"
    assert set(candidate) == {
        "topic_draft", "source_url", "source_title_reference",
        "source_published_at", "proposed_category_ref", "review_status",
        "publication_status", "publish_authorization", "independent_source_verified",
    }


def test_p02_e01_timeout_is_unknown_without_retry_or_downstream_calls(pipeline):
    preview = run_s1(pipeline, error=TimeoutError("SYNTHETIC_TIMEOUT_PRIVATE_MARKER"))
    pipeline.normalize.assert_not_called()
    pipeline.parse.assert_not_called()
    pipeline.validate.assert_not_called()
    assert [event[0] for event in pipeline.events.mock_calls] == ["read"]
    assert_preview(preview, status="UPSTREAM_ERROR", search="UNKNOWN",
                   validation="NOT_EVALUATED", calls=None)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    # Exact Adapter reason-code spelling is not frozen; never copy exception text.
    assert "SYNTHETIC_TIMEOUT_PRIVATE_MARKER" not in json.dumps(preview)


def test_p05_valid_empty_result_is_not_search_or_structure_failure(pipeline):
    payload = payload_for("P-05")
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_preview(preview, status="EMPTY_RESULT", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == []


def test_p07_all_candidates_rejected_preserves_valid_response_and_issue(pipeline):
    payload = payload_for("P-07")
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_preview(preview, status="NO_VALID_CANDIDATES", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["candidates"] == []
    assert preview["issues"] == [{
        "candidate_index": 0, "code": "CITATION_URL_MISMATCH",
    }]
    assert preview["reason_codes"] == []


def test_p08_broken_output_is_invalid_with_unobserved_calls(pipeline):
    payload = payload_for("P-08")
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=False)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE", search="UNKNOWN",
                   validation="INVALID", calls=None)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == ["RESPONSE_STRUCTURE_INVALID"]
