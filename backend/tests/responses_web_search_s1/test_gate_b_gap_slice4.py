"""B-gap Slice 4: frozen D-02/03/04/07/08/09 through the real S1 Service.

Gate A inputs are preserved; no annotation synthesis from candidate URLs.
Successful parsing uses assert_flow; Parser failures use the separate
short-circuit helper. Both retain actual Normalizer-to-Parser identity checks.
Preview expectations come from the frozen contract, not production results.
Mock read-once, no S0 service, input deep-copy and import/I/O guards are reused.
Gate B HOLD, Gate C/D unverified, G5/G6 HOLD, P4 NOT FROZEN remain unchanged.
"""

import copy
import json

import pytest

from .fixtures import URL, content, response
from .test_gate_a_followup import OTHER_URL, base_candidate, set_candidates
from .test_gate_b_gap_slice3 import assert_normalized_evidence, assert_review_candidate
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)
from .test_gate_b_preview_remaining import assert_parser_short_circuit


def assert_parser_failure(pipeline, payload, *, reason):
    original_text = content(payload)["text"]
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=1, searches=1)
    result = assert_normalized_evidence(pipeline)
    assert result.parser_input["output"][1]["content"][0]["text"] == original_text
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=1)
    assert preview["reason_codes"] == [reason]
    assert preview["issues"] == preview["candidates"] == []


def assert_validated(pipeline, payload, *, status, issue):
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_normalized_evidence(pipeline)
    assert_preview(preview, status=status, search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["reason_codes"] == []
    assert preview["issues"] == [issue]
    return preview, pipeline.validate.call_args.args[0]


def test_d02_file_url_does_not_rewrite_valid_citation(pipeline):
    payload = response()
    raw = base_candidate()
    raw["source_url"] = "file:///private"
    set_candidates(payload, [raw])
    assert content(payload)["annotations"] == content(response())["annotations"]
    preview, parsed = assert_validated(
        pipeline, payload, status="NO_VALID_CANDIDATES",
        issue={"candidate_index": 0, "code": "SOURCE_URL_INVALID"},
    )
    assert parsed.candidates == (raw,)
    assert parsed.citation_urls == frozenset({URL})
    assert preview["candidates"] == []


def test_d03_valid_candidate_and_field_issue_are_both_preserved(pipeline):
    payload = response()
    invalid = {"topic_draft": "필드 오류 주제", "source_url": OTHER_URL}
    set_candidates(payload, [base_candidate(), invalid])
    preview, parsed = assert_validated(
        pipeline, payload, status="PREVIEW_READY",
        issue={"candidate_index": 1, "code": "CANDIDATE_FIELDS_INVALID"},
    )
    assert parsed.candidates == (base_candidate(), invalid)
    assert_review_candidate(preview)


def test_d04_four_candidates_reach_parser_without_truncation(pipeline):
    payload = response()
    candidates = [
        {**base_candidate(), "topic_draft": f"합성 주제 {index}",
         "source_url": f"https://vendor.example.test/releases/{index}"}
        for index in range(1, 5)
    ]
    set_candidates(payload, candidates)
    assert len(json.loads(content(payload)["text"])["candidates"]) == 4
    assert_parser_failure(pipeline, payload, reason="CANDIDATE_LIMIT_EXCEEDED")
    projected = pipeline.parse.call_args.args[0]
    assert json.loads(projected["output"][1]["content"][0]["text"]) == {
        "candidates": candidates,
    }


@pytest.mark.parametrize("duplicate", ["url", "topic"])
def test_d07_duplicate_keeps_first_and_reports_second(pipeline, duplicate):
    payload = response()
    second = base_candidate()
    expected_citations = {URL}
    if duplicate == "url":
        second["topic_draft"] = "다른 합성 주제"
    else:
        second.update(topic_draft="  가상   기기 출시  ", source_url=OTHER_URL)
        citation = copy.deepcopy(content(payload)["annotations"][0])
        citation["url"] = OTHER_URL
        content(payload)["annotations"].append(citation)
        expected_citations.add(OTHER_URL)
    set_candidates(payload, [base_candidate(), second])
    preview, parsed = assert_validated(
        pipeline, payload, status="PREVIEW_READY",
        issue={"candidate_index": 1, "code": "DUPLICATE_CANDIDATE"},
    )
    assert parsed.candidates == (base_candidate(), second)
    assert parsed.citation_urls == frozenset(expected_citations)
    assert_review_candidate(preview)


@pytest.mark.parametrize("candidates", [{}, None], ids=["object", "null"])
def test_d08_candidate_container_is_not_coerced_in_service(candidates, pipeline):
    payload = response()
    content(payload)["text"] = json.dumps({"candidates": candidates})
    assert_parser_failure(pipeline, payload, reason="RESPONSE_STRUCTURE_INVALID")


@pytest.mark.parametrize("defect,reason", [
    ("missing", "RESPONSE_STRUCTURE_INVALID"),
    ("non-list", "RESPONSE_STRUCTURE_INVALID"),
    ("missing-url", "ANNOTATION_STRUCTURE_INVALID"),
])
def test_d09_empty_candidates_do_not_bypass_parser_structure(defect, reason, pipeline):
    payload = response()
    content(payload)["text"] = '{"candidates":[]}'
    if defect == "missing":
        del content(payload)["annotations"]
    elif defect == "non-list":
        content(payload)["annotations"] = {}
    else:
        del content(payload)["annotations"][0]["url"]
    assert_parser_failure(pipeline, payload, reason=reason)
