"""Frozen citation/candidate/cross-error AC, exercised against real S0.

Trace coordinates identify original metadata only. Passing URL membership does
not establish source truth, rights, or semantic support for any candidate.
Gate B Preview status/safety assertions remain a separate task.
"""

import copy
import importlib
import json

import pytest

from .fixtures import TEXT, URL, content, reasoning, response
from .test_gate_a import (
    assert_accepted,
    assert_normalized,
    assert_rejected,
    normalize,
    s0,
)

OTHER_URL = "https://vendor.example.test/releases/2"


def base_candidate():
    return json.loads(TEXT)["candidates"][0]


def set_candidates(payload, candidates):
    # Never regenerate annotations from candidate URLs.
    content(payload)["text"] = json.dumps(
        {"candidates": candidates}, ensure_ascii=False, separators=(",", ":"),
    )


def issue_pairs(issues):
    return [(issue.candidate_index, issue.code) for issue in issues]


def test_c02_changed_citation_url_does_not_rewrite_candidate(monkeypatch):
    payload = response()
    content(payload)["annotations"][0]["url"] = OTHER_URL
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.candidates[0]["source_url"] == URL
    assert parsed.citation_urls == frozenset({OTHER_URL})
    assert accepted == ()
    assert issue_pairs(issues) == [(0, "CITATION_URL_MISMATCH")]
    assert len(result.citation_trace) == 1
    trace = result.citation_trace[0]
    assert (
        trace.output_index, trace.content_index, trace.annotation_index,
    ) == (1, 0, 0)
    assert (trace.url, trace.start_index, trace.end_index) == (OTHER_URL, 55, 93)


@pytest.mark.parametrize("citation_url", [
    "HTTPS://vendor.example.test/releases/1",
    "https://VENDOR.example.test/releases/1",
    "https://vendor.example.test/releases/1#details",
], ids=["scheme-case", "host-case", "fragment"])
def test_c04_citation_requires_original_string_equality(citation_url, monkeypatch):
    payload = response()
    content(payload)["annotations"][0]["url"] = citation_url
    assert citation_url != URL
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.candidates[0]["source_url"] == URL
    assert parsed.citation_urls == frozenset({citation_url})
    assert result.citation_trace[0].url == citation_url
    assert accepted == ()
    assert issue_pairs(issues) == [(0, "CITATION_URL_MISMATCH")]


@pytest.mark.parametrize("start,end", [(0, 5), (14, 19)], ids=["C-05c", "F-05"])
def test_offsets_preserve_original_coordinates_without_semantic_claims(
    start, end, monkeypatch,
):
    payload = response()
    text_part = content(payload)
    text_part["annotations"][0].update(start_index=start, end_index=end)
    second = copy.deepcopy(text_part["annotations"][0])
    second.update(start_index=6, end_index=10)
    text_part["annotations"].append(second)
    assert 0 <= start < end < 55
    assert TEXT[start:end] != URL
    # Original message output index becomes 3, projected message index stays 1.
    payload["output"].insert(0, reasoning(0))
    payload["output"].insert(2, reasoning(1))
    result = normalize(payload, monkeypatch)
    assert_normalized(result, text_part)
    assert_accepted(result)
    assert [
        (trace.output_index, trace.content_index, trace.annotation_index,
         trace.url, trace.start_index, trace.end_index)
        for trace in result.citation_trace
    ] == [(3, 0, 0, URL, start, end), (3, 0, 1, URL, 6, 10)]
    assert payload["output"][3]["content"][0] == text_part
    # This proves metadata preservation and S0 URL membership, not that either
    # span supports the candidate's claim. No offset validity policy is added.


def test_c06_partial_citation_mismatch_preserves_valid_candidate_and_issue(monkeypatch):
    payload = response()
    second = base_candidate()
    second.update(topic_draft="별도 합성 주제", source_url=OTHER_URL)
    set_candidates(payload, [base_candidate(), second])
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert len(parsed.candidates) == 2
    assert parsed.citation_urls == frozenset({URL})
    assert [candidate.source_url for candidate in accepted] == [URL]
    assert issue_pairs(issues) == [(1, "CITATION_URL_MISMATCH")]


def test_d03_partial_field_error_preserves_valid_candidate_and_issue(monkeypatch):
    payload = response()
    set_candidates(payload, [base_candidate(), {
        "topic_draft": "필드 오류 주제", "source_url": OTHER_URL,
    }])
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert len(parsed.candidates) == 2
    assert [candidate.source_url for candidate in accepted] == [URL]
    assert issue_pairs(issues) == [(1, "CANDIDATE_FIELDS_INVALID")]


def test_d04_four_candidates_are_not_truncated_before_s0(monkeypatch):
    payload = response()
    candidates = [
        {**base_candidate(), "topic_draft": f"합성 주제 {index}",
         "source_url": f"https://vendor.example.test/releases/{index}"}
        for index in range(1, 5)
    ]
    set_candidates(payload, candidates)
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert parsed.reason_codes == ("CANDIDATE_LIMIT_EXCEEDED",)
    assert parsed.candidates == accepted == issues == ()
    validator = importlib.import_module("app.responses_web_search.validator")
    validator.validate_candidates.assert_not_called()


@pytest.mark.parametrize("duplicate", ["url", "topic"])
def test_d07_duplicate_url_or_normalized_topic_keeps_first(duplicate, monkeypatch):
    payload = response()
    second = base_candidate()
    if duplicate == "url":
        second["topic_draft"] = "다른 합성 주제"
    else:
        second.update(topic_draft="  가상   기기 출시  ", source_url=OTHER_URL)
        citation = copy.deepcopy(content(payload)["annotations"][0])
        citation["url"] = OTHER_URL
        content(payload)["annotations"].append(citation)
    set_candidates(payload, [base_candidate(), second])
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert len(parsed.candidates) == 2
    assert len(accepted) == 1
    assert accepted[0].source_url == URL
    assert accepted[0].topic_draft == "가상 기기 출시"
    assert issue_pairs(issues) == [(1, "DUPLICATE_CANDIDATE")]


def test_f06_one_citation_for_shared_url_proves_only_s0_deduplication(monkeypatch):
    payload = response()
    second = base_candidate()
    second["topic_draft"] = "같은 출처에 대한 별개의 합성 주장"
    set_candidates(payload, [base_candidate(), second])
    assert len(content(payload)["annotations"]) == 1
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert [item["source_url"] for item in parsed.candidates] == [URL, URL]
    assert parsed.candidates[1]["topic_draft"] == "같은 출처에 대한 별개의 합성 주장"
    assert parsed.citation_urls == frozenset({URL})
    assert len(result.citation_trace) == 1
    trace = result.citation_trace[0]
    assert (
        trace.output_index, trace.content_index, trace.annotation_index,
    ) == (1, 0, 0)
    assert (trace.url, trace.start_index, trace.end_index) == (URL, 55, 93)
    assert len(accepted) == 1
    assert accepted[0].topic_draft == "가상 기기 출시"
    assert issue_pairs(issues) == [(1, "DUPLICATE_CANDIDATE")]
    # A URL set and a single trace do not express support for both claims.


def test_x03_refusal_blocks_independently_valid_s0_candidates(monkeypatch):
    payload = response()
    parser = importlib.import_module("app.responses_web_search.parser")
    validator = importlib.import_module("app.responses_web_search.validator")
    config = importlib.import_module("app.responses_web_search.types").SearchRunConfig()
    parsed = parser.parse_response(payload, config)
    assert parsed.status is None
    accepted, issues = validator.validate_candidates(parsed)
    assert len(accepted) == 1
    assert accepted[0].source_url == URL
    assert issues == ()
    # Adding refusal must invalidate the whole response, despite this valid part.
    payload["output"][1]["content"].append({
        "type": "refusal", "refusal": "SYNTHETIC_X03_REFUSAL",
    })
    result = normalize(payload, monkeypatch)
    assert_rejected(result)
