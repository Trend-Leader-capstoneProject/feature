"""First Red slice of frozen v0.2.2 (synthetic compatibility only).

Test binding for the document's proposed internal interface:
app.responses_web_search.normalizer.normalize_response(response, config),
returning attributes outcome, execution_evidence, parser_input, reason_codes.
execution_evidence has the attributes named in frozen section 2.2.
This is a project test binding, not an SDK/public API contract.
Imports are deferred to test execution; missing S1 must never break collection.

Covered Gate A portions: A-01/A-04, B-01/B-02/B-06, C-03/C-05a/C-05b,
D-05, L-01..L-06. S1 Preview and production orchestration are NOT tested by
the S0 integration helper below; their Gate B assertions remain pending.

Remaining Gate A/B AC IDs (59 of 74; no implicit coverage claims):
A-02/A-03/A-05..A-09; B-03..B-05/B-07..B-09;
C-01/C-02/C-04/C-05c/C-06..C-08; D-01..D-04/D-06..D-09;
E-01..E-03/E-04a..E-04c/E-05..E-07/E-09/E-10;
F-01..F-06; P-01..P-08; X-01..X-06.
Also pending: Gate B Preview assertions for the 15 selected AC IDs,
citation_trace diagnostics, and full production S0 non-call orchestration.
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
