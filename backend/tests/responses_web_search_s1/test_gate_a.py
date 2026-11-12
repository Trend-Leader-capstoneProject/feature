"""Red slices 1 through 3 of frozen v0.2.2 (synthetic compatibility only).

Test binding for the document's proposed internal interface:
app.responses_web_search.normalizer.normalize_response(response, config),
returning attributes outcome, execution_evidence, parser_input, reason_codes.
execution_evidence has the attributes named in frozen section 2.2.
This is a project test binding, not an SDK/public API contract.
Imports are deferred to test execution; missing S1 must never break collection.

Covered Gate A portions: A-01..A-09, B-01..B-09, C-03/C-05a/C-05b/C-08,
D-01/D-02/D-05, L-01..L-06, X-06. Preview and orchestration are NOT tested by
the S0 integration helper below; their Gate B assertions remain pending.
Follow-up module additionally covers C-02/C-04/C-05c/C-06, D-03/D-04/D-07,
F-05/F-06, X-03 and original citation_trace coordinates (42 AC portions total).

Remaining Gate A/B AC IDs (32 of 74; no implicit coverage claims):
C-01/C-07; D-06/D-08/D-09;
E-01..E-03/E-04a..E-04c/E-05..E-07/E-09/E-10;
F-01..F-04; P-01..P-08; X-01/X-02/X-04/X-05.
Also pending: Gate B Preview assertions for the 42 selected AC IDs,
remaining citation diagnostics and full production S0 non-call orchestration.
E-08 belongs exclusively to Gate C; Gate C/D remain unverified.
"""

import copy
import importlib
from unittest.mock import Mock

import pytest

from .fixtures import TEXT, URL, content, padded_response, reasoning, response


def normalize(payload, monkeypatch):
    """Observe forbidden S0 calls inside Normalizer, without faking its result."""
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    parser_spy = Mock(wraps=parser.parse_response)
    validator_spy = Mock(wraps=validator.validate_candidates)
    monkeypatch.setattr(parser, "parse_response", parser_spy)
    monkeypatch.setattr(validator, "validate_candidates", validator_spy)
    original = copy.deepcopy(payload)
    # This exact absent module is the expected first Red. No exception is caught:
    # a transitive import failure must remain distinguishable from missing S1.
    module = importlib.import_module("app.responses_web_search.normalizer")
    config_type = importlib.import_module(
        "app.responses_web_search.types"
    ).SearchRunConfig
    result = module.normalize_response(payload, config_type())
    assert payload == original
    parser_spy.assert_not_called()
    validator_spy.assert_not_called()
    return result


def s0(result):
    """Use real S0 only after successful normalization; no S1 Preview replica."""
    assert result.outcome == "NORMALIZED"
    assert isinstance(result.parser_input, dict)
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    types = importlib.import_module("app.responses_web_search.types")
    parsed = parser.parse_response(result.parser_input, types.SearchRunConfig())
    if parsed.status is not None:
        return parsed, (), ()
    accepted, issues = validator.validate_candidates(parsed)
    return parsed, accepted, issues


def assert_normalized(result, expected_content):
    assert result.outcome == "NORMALIZED"
    assert result.execution_evidence.response_status == "completed"
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == 1
    projected = result.parser_input["output"]
    assert [item["type"] for item in projected] == ["web_search_call", "message"]
    assert projected[0]["status"] == "completed"
    assert projected[0]["action"]["type"] == "search"
    assert projected[1]["content"] == [expected_content]


def assert_accepted(result):
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.tool_calls_observed == 1
    assert parsed.citation_urls == frozenset({URL})
    assert issues == ()
    assert len(accepted) == 1
    assert accepted[0].topic_draft == "가상 기기 출시"
    assert accepted[0].source_url == URL
    assert accepted[0].source_title_reference == "가상 공식 발표"


def assert_rejected(result, reason=None, calls=1, searches=1):
    assert result.outcome == "REJECTED"
    assert result.parser_input is None
    assert result.execution_evidence.web_search_calls_observed == calls
    assert result.execution_evidence.completed_search_actions == searches
    if reason is not None:
        assert reason in result.reason_codes


@pytest.mark.parametrize("size", [None, 32768, 32769], ids=["F-BASE", "L-01", "L-02"])
def test_fixture_preconditions_independently_of_s1(size, isolated_session):
    # L-02 is valid for S0 alone; its rejection must come from the S1 byte cap.
    payload = response() if size is None else padded_response(size)
    assert content(payload)["text"][55:93] == URL
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    types = importlib.import_module("app.responses_web_search.types")
    parsed = parser.parse_response(payload, types.SearchRunConfig())
    assert parsed.status is None
    accepted, issues = validator.validate_candidates(parsed)
    assert len(accepted) == 1
    assert accepted[0].source_url == URL
    assert issues == ()


def test_a01_normal_search(monkeypatch, isolated_session):
    payload = response()
    assert TEXT[55:93] == URL
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(response()))
    assert_accepted(result)


def test_a04_original_two_calls_cannot_be_hidden(monkeypatch):
    payload = response()
    extra = copy.deepcopy(payload["output"][0])
    extra["id"] = "ws_synthetic_second"
    payload["output"].append(extra)
    assert sum(item["type"] == "web_search_call" for item in payload["output"]) == 2
    result = normalize(payload, monkeypatch)
    assert_rejected(result, "TOOL_CALL_LIMIT_EXCEEDED", calls=2, searches=2)


@pytest.mark.parametrize("status", ["completed", None], ids=["B-01", "B-02"])
def test_b01_b02_reasoning_status_is_optional(status, monkeypatch):
    payload = response()
    auxiliary = reasoning()
    if status is None:
        del auxiliary["status"]
    payload["output"].append(auxiliary)
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(response()))
    assert_accepted(result)


def test_b06_refusal_blocks_otherwise_valid_candidates(monkeypatch):
    payload = response()
    payload["output"][1]["content"].append({
        "type": "refusal", "refusal": "SYNTHETIC_REFUSAL_PRIVATE_MARKER",
    })
    result = normalize(payload, monkeypatch)
    assert_rejected(result)
    assert "SYNTHETIC_REFUSAL_PRIVATE_MARKER" not in repr(result.reason_codes)


def test_c03_sources_cannot_replace_annotations(monkeypatch):
    payload = response()
    content(payload)["annotations"] = []
    payload["output"][0]["action"]["sources"] = [{"type": "url", "url": URL}]
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.citation_urls == frozenset()
    assert accepted == ()
    assert [(issue.candidate_index, issue.code) for issue in issues] == [
        (0, "CITATION_URL_MISMATCH"),
    ]


@pytest.mark.parametrize("url", [None, 42], ids=["missing-url", "non-string-url"])
def test_c05a_annotation_url_structure_remains_s0_responsibility(url, monkeypatch):
    payload = response()
    annotation = content(payload)["annotations"][0]
    if url is None:
        del annotation["url"]
    else:
        annotation["url"] = url
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert parsed.reason_codes == ("ANNOTATION_STRUCTURE_INVALID",)
    assert parsed.candidates == accepted == issues == ()


@pytest.mark.parametrize("annotations", [None, {}], ids=["missing", "non-list"])
def test_c05b_annotation_container_remains_s0_responsibility(annotations, monkeypatch):
    payload = response()
    if annotations is None:
        del content(payload)["annotations"]
    else:
        content(payload)["annotations"] = annotations
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert parsed.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
    assert parsed.candidates == accepted == issues == ()


def test_d05_json_error_is_not_empty_success(monkeypatch):
    payload = response()
    content(payload)["text"] = TEXT[:-1]
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert parsed.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
    assert parsed.candidates == accepted == issues == ()


@pytest.mark.parametrize("size", [32768, 32769], ids=["L-01", "L-02"])
def test_l01_l02_utf8_byte_boundary(size, monkeypatch):
    payload = padded_response(size)
    assert len(content(payload)["text"].encode("utf-8")) == size
    assert len(content(payload)["text"]) < 32768
    result = normalize(payload, monkeypatch)
    if size == 32768:
        assert_normalized(result, content(payload))
        assert_accepted(result)
    else:
        assert_rejected(result, "S1_TEXT_BYTES_LIMIT_EXCEEDED")


@pytest.mark.parametrize("count", [16, 17], ids=["L-03", "L-04"])
def test_l03_l04_output_count_before_filtering(count, monkeypatch):
    payload = response()
    payload["output"].extend(reasoning(index) for index in range(count - 2))
    assert len(payload["output"]) == count
    result = normalize(payload, monkeypatch)
    if count == 16:
        assert_normalized(result, content(payload))
        assert_accepted(result)
    else:
        assert_rejected(result, "S1_OUTPUT_ITEMS_LIMIT_EXCEEDED")


@pytest.mark.parametrize("count", [32, 33], ids=["L-05", "L-06"])
def test_l05_l06_annotation_count_without_truncation(count, monkeypatch):
    payload = response()
    annotation = content(payload)["annotations"][0]
    content(payload)["annotations"] = [copy.deepcopy(annotation) for _ in range(count)]
    result = normalize(payload, monkeypatch)
    if count == 32:
        assert_normalized(result, content(payload))
        assert_accepted(result)
    else:
        assert_rejected(result, "S1_ANNOTATIONS_LIMIT_EXCEEDED")


def assert_search_not_executed(result, calls):
    assert result.outcome == "NORMALIZED"
    assert result.execution_evidence.response_status == "completed"
    assert result.execution_evidence.web_search_calls_observed == calls
    assert result.execution_evidence.completed_search_actions == 0
    assert result.execution_evidence.assistant_messages_observed == 1
    parsed, accepted, issues = s0(result)
    assert parsed.status == "SEARCH_NOT_EXECUTED"
    assert parsed.tool_calls_observed == calls
    assert parsed.simulated_web_search_executed is False
    assert parsed.candidates == accepted == issues == ()
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    parser.parse_response.assert_called_once()
    validator.validate_candidates.assert_not_called()


def test_a02_absent_search_is_not_fabricated(monkeypatch):
    payload = response()
    del payload["output"][0]
    assert [item["type"] for item in payload["output"]] == ["message"]
    result = normalize(payload, monkeypatch)
    assert_search_not_executed(result, calls=0)
    assert [item["type"] for item in result.parser_input["output"]] == ["message"]
    assert result.parser_input["output"][0]["content"] == [content(response())]


def test_a03_open_page_is_not_search_evidence(monkeypatch):
    payload = response()
    payload["output"][0]["action"]["type"] = "open_page"
    result = normalize(payload, monkeypatch)
    assert_search_not_executed(result, calls=1)
    projected = result.parser_input["output"]
    assert [item["type"] for item in projected] == ["web_search_call", "message"]
    assert projected[0]["status"] == "completed"
    assert projected[0]["action"]["type"] == "open_page"
    assert projected[1]["content"] == [content(response())]


def test_a05_failed_tool_is_not_promoted_to_completed(monkeypatch):
    payload = response()
    payload["output"][0]["status"] = "failed"
    result = normalize(payload, monkeypatch)
    assert_rejected(result, calls=1, searches=0)


def test_a06_incomplete_response_is_rejected(monkeypatch):
    payload = response()
    payload["status"] = "incomplete"
    result = normalize(payload, monkeypatch)
    # Top-level rejection does not invent an observation-count policy.
    assert result.outcome == "REJECTED"
    assert result.parser_input is None


def test_b03_explicit_incomplete_reasoning_cannot_be_discarded(monkeypatch):
    payload = response()
    auxiliary = reasoning()
    auxiliary["status"] = "incomplete"
    payload["output"].append(auxiliary)
    result = normalize(payload, monkeypatch)
    assert_rejected(result)


def test_b04_two_assistant_messages_cannot_be_selected_or_merged(monkeypatch):
    payload = response()
    second = copy.deepcopy(payload["output"][1])
    second["id"] = "msg_synthetic_second"
    payload["output"].append(second)
    assert sum(item["type"] == "message" for item in payload["output"]) == 2
    result = normalize(payload, monkeypatch)
    assert_rejected(result)
    assert result.execution_evidence.assistant_messages_observed == 2


def test_b05_two_output_text_blocks_cannot_be_selected_or_merged(monkeypatch):
    payload = response()
    payload["output"][1]["content"].append(copy.deepcopy(content(payload)))
    assert len(payload["output"][1]["content"]) == 2
    result = normalize(payload, monkeypatch)
    assert_rejected(result)


def test_x06_original_evidence_overrides_one_call_projection(monkeypatch):
    payload = response()
    second = copy.deepcopy(payload["output"][0])
    second["id"] = "ws_synthetic_second"
    payload["output"].append(second)
    original = copy.deepcopy(payload)
    assert sum(item["type"] == "web_search_call" for item in original["output"]) == 2

    # Independent counterexample: S0 alone cannot detect a call hidden upstream.
    # This is a deliberately altered fixture, never a fake Normalizer result.
    truncated = copy.deepcopy(original)
    del truncated["output"][-1]
    assert sum(item["type"] == "web_search_call" for item in truncated["output"]) == 1
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    config = importlib.import_module("app.responses_web_search.types").SearchRunConfig()
    raw_parsed = parser.parse_response(original, config)
    assert raw_parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert raw_parsed.reason_codes == ("TOOL_CALL_LIMIT_EXCEEDED",)
    assert raw_parsed.tool_calls_observed == 2
    assert raw_parsed.candidates == ()
    truncated_parsed = parser.parse_response(truncated, config)
    assert truncated_parsed.status is None
    assert truncated_parsed.tool_calls_observed == 1
    accepted, issues = validator.validate_candidates(truncated_parsed)
    assert len(accepted) == 1
    assert accepted[0].source_url == URL
    assert issues == ()

    # Pass the complete original, never the truncated counterpart, to S1.
    result = normalize(payload, monkeypatch)
    assert payload == original
    assert_rejected(result, "TOOL_CALL_LIMIT_EXCEEDED", calls=2, searches=2)


def test_a07_missing_action_type_cannot_be_inferred(monkeypatch):
    payload = response()
    del payload["output"][0]["action"]["type"]
    result = normalize(payload, monkeypatch)
    assert result.outcome == "REJECTED"
    assert result.parser_input is None
    assert result.execution_evidence.web_search_calls_observed == 1


def test_a08_unknown_output_cannot_be_silently_removed(monkeypatch):
    payload = response()
    payload["output"].append({
        "id": "unknown_synthetic_output", "type": "synthetic_unsupported_output",
        "status": "completed",
    })
    result = normalize(payload, monkeypatch)
    assert_rejected(result)


def test_a09_find_in_page_is_not_search_evidence(monkeypatch):
    payload = response()
    payload["output"][0]["action"]["type"] = "find_in_page"
    result = normalize(payload, monkeypatch)
    assert_search_not_executed(result, calls=1)
    projected = result.parser_input["output"]
    assert [item["type"] for item in projected] == ["web_search_call", "message"]
    assert projected[0]["status"] == "completed"
    assert projected[0]["action"]["type"] == "find_in_page"
    assert projected[1]["content"] == [content(response())]


def test_b07_missing_assistant_message_is_not_empty_success(monkeypatch):
    payload = response()
    del payload["output"][1]
    result = normalize(payload, monkeypatch)
    assert_rejected(result)
    assert result.execution_evidence.assistant_messages_observed == 0


def test_b08_unknown_content_cannot_be_silently_removed(monkeypatch):
    payload = response()
    payload["output"][1]["content"].append({"type": "synthetic_unsupported_content"})
    result = normalize(payload, monkeypatch)
    assert_rejected(result)


@pytest.mark.parametrize(
    "phase", [None, "final_answer"], ids=["absent", "final_answer"],
)
def test_b09_single_message_phase_is_optional(phase, monkeypatch):
    payload = response()
    if phase is not None:
        payload["output"][1]["phase"] = phase
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(response()))
    assert_accepted(result)


def test_c08_mixed_unsupported_annotation_cannot_be_discarded(monkeypatch):
    payload = response()
    content(payload)["annotations"].append({"type": "synthetic_unsupported_annotation"})
    assert content(payload)["annotations"][0] == content(response())["annotations"][0]
    result = normalize(payload, monkeypatch)
    assert_rejected(result)


def test_d01_empty_candidates_preserve_successful_search(monkeypatch):
    payload = response()
    content(payload)["text"] = '{"candidates":[]}'
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    # EMPTY_RESULT is a Gate B Preview status; S0 parsing itself succeeds.
    assert parsed.status is None
    assert parsed.simulated_web_search_executed is True
    assert parsed.tool_calls_observed == 1
    assert parsed.citation_urls == frozenset({URL})
    assert parsed.reason_codes == ()
    assert parsed.candidates == accepted == issues == ()
    validator = importlib.import_module("app.responses_web_search.validator")
    validator.validate_candidates.assert_called_once_with(parsed)


def test_d02_file_url_rejected_by_s0_without_rewriting_citation(monkeypatch):
    payload = response()
    content(payload)["text"] = TEXT.replace(URL, "file:///private")
    assert content(payload)["annotations"] == content(response())["annotations"]
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.simulated_web_search_executed is True
    assert parsed.candidates[0]["source_url"] == "file:///private"
    assert parsed.citation_urls == frozenset({URL})
    assert accepted == ()
    assert [(issue.candidate_index, issue.code) for issue in issues] == [
        (0, "SOURCE_URL_INVALID"),
    ]
