"""B-gap Slice 3: frozen C-03/04/05a/05b/05c/06/07 through real S1.

Original Gate A variants are reused; Preview expectations are independent.
Offsets trace original coordinates only, not semantic support or SDK validity.
Reasoning projection is checked separately from unchanged-output assert_flow.
run_s1 retains Mock read-once, no S0 service, deep-copy and import/I/O guards.
Gate B HOLD, Gate C/D unverified, G5/G6 HOLD, P4 NOT FROZEN remain unchanged.
"""

import copy

import pytest

from .fixtures import TEXT, URL, content, reasoning, response
from .test_gate_a_followup import OTHER_URL, base_candidate, set_candidates
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)
from .test_gate_b_preview_remaining import assert_parser_short_circuit


def assert_review_candidate(preview, *, topic="가상 기기 출시"):
    assert preview["candidates"] == [{
        "topic_draft": topic, "source_url": URL,
        "source_title_reference": "가상 공식 발표",
        "source_published_at": None, "proposed_category_ref": "IT_DIGITAL",
        "review_status": "REVIEW_REQUIRED",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE", "independent_source_verified": False,
    }]


def assert_normalized_evidence(pipeline):
    result, = pipeline.normalization_results
    assert result.outcome == "NORMALIZED"
    assert result.reason_codes == ()
    assert result.execution_evidence.response_status == "completed"
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == 1
    return result


def assert_mismatch_preview(preview):
    assert_preview(preview, status="NO_VALID_CANDIDATES", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["candidates"] == preview["reason_codes"] == []
    assert preview["issues"] == [{
        "candidate_index": 0, "code": "CITATION_URL_MISMATCH",
    }]


def test_c03_sources_do_not_replace_missing_candidate_citation(pipeline):
    payload = response()
    content(payload)["annotations"] = []
    payload["output"][0]["action"]["sources"] = [{"type": "url", "url": URL}]
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    result = assert_normalized_evidence(pipeline)
    assert result.parser_input["output"][1]["content"][0]["annotations"] == []
    assert result.citation_trace == ()
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.candidates[0]["source_url"] == URL
    assert parsed.citation_urls == frozenset()
    assert_mismatch_preview(preview)


@pytest.mark.parametrize("citation_url", [
    "HTTPS://vendor.example.test/releases/1",
    "https://VENDOR.example.test/releases/1",
    "https://vendor.example.test/releases/1#details",
], ids=["scheme-case", "host-case", "fragment"])
def test_c04_citation_requires_original_url_through_s1(citation_url, pipeline):
    payload = response()
    content(payload)["annotations"][0]["url"] = citation_url
    assert citation_url != URL
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    result = assert_normalized_evidence(pipeline)
    assert result.citation_trace[0].url == citation_url
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.candidates[0]["source_url"] == URL
    assert parsed.citation_urls == frozenset({citation_url})
    assert_mismatch_preview(preview)


@pytest.mark.parametrize("defect,reason", [
    ("missing-url", "ANNOTATION_STRUCTURE_INVALID"),
    ("non-string-url", "ANNOTATION_STRUCTURE_INVALID"),
    ("missing-container", "RESPONSE_STRUCTURE_INVALID"),
    ("non-list-container", "RESPONSE_STRUCTURE_INVALID"),
], ids=["C-05a-missing", "C-05a-non-string", "C-05b-missing", "C-05b-non-list"])
def test_c05a_c05b_annotation_structure_stays_parser_responsibility(
    defect, reason, pipeline,
):
    payload = response()
    if defect == "missing-url":
        del content(payload)["annotations"][0]["url"]
    elif defect == "non-string-url":
        content(payload)["annotations"][0]["url"] = 42
    elif defect == "missing-container":
        del content(payload)["annotations"]
    else:
        content(payload)["annotations"] = {}
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=1, searches=1)
    assert_normalized_evidence(pipeline)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=1)
    assert preview["reason_codes"] == [reason]
    assert preview["issues"] == preview["candidates"] == []


def test_c05c_original_trace_survives_reasoning_projection_without_verification(
    pipeline,
):
    payload = response()
    text_part = content(payload)
    text_part["annotations"][0].update(start_index=0, end_index=5)
    second = copy.deepcopy(text_part["annotations"][0])
    second.update(start_index=6, end_index=10)
    text_part["annotations"].append(second)
    assert TEXT[0:5] != URL and TEXT[6:10] != URL
    expected_output = copy.deepcopy(payload["output"])
    payload["output"].insert(0, reasoning(0))
    payload["output"].insert(2, reasoning(1))
    preview = run_s1(pipeline, payload=payload)
    pipeline.normalize.assert_called_once_with(payload, pipeline.config)
    result = assert_normalized_evidence(pipeline)
    pipeline.parse.assert_called_once_with(result.parser_input, pipeline.config)
    assert pipeline.parse.call_args.args[0] is result.parser_input
    assert result.parser_input["status"] == "completed"
    assert result.parser_input["output"] == expected_output
    assert [item["type"] for item in result.parser_input["output"]] == [
        "web_search_call", "message",
    ]
    assert [
        (trace.output_index, trace.content_index, trace.annotation_index,
         trace.url, trace.start_index, trace.end_index)
        for trace in result.citation_trace
    ] == [(3, 0, 0, URL, 0, 5), (3, 0, 1, URL, 6, 10)]
    pipeline.validate.assert_called_once()
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.status is None
    assert parsed.citation_urls == frozenset({URL})
    assert [event[0] for event in pipeline.events.mock_calls] == [
        "read", "normalize", "parse", "validate",
    ]
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert_review_candidate(preview)
    assert preview["issues"] == preview["reason_codes"] == []
    # Internal trace need not be copied into Preview; no new offset policy.


def test_c06_partial_success_preserves_second_candidate_issue(pipeline):
    payload = response()
    second = base_candidate()
    second.update(topic_draft="별도 합성 주제", source_url=OTHER_URL)
    set_candidates(payload, [base_candidate(), second])
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_normalized_evidence(pipeline)
    parsed = pipeline.validate.call_args.args[0]
    assert len(parsed.candidates) == 2
    assert parsed.candidates[1] == second
    assert parsed.citation_urls == frozenset({URL})
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert_review_candidate(preview)
    assert preview["reason_codes"] == []
    assert preview["issues"] == [{
        "candidate_index": 1, "code": "CITATION_URL_MISMATCH",
    }]


def test_c07_matching_url_does_not_certify_contradictory_source_claim(pipeline):
    payload = response()
    raw = base_candidate()
    raw["topic_draft"] = "합성 기기가 출시되었다"
    set_candidates(payload, [raw])
    content(payload)["annotations"][0]["title"] = "합성 출처 설명: 출시 계획이 없다"
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    assert_normalized_evidence(pipeline)
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.candidates == (raw,)
    assert parsed.citation_urls == frozenset({URL})
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert_review_candidate(preview, topic="합성 기기가 출시되었다")
    assert preview["reason_codes"] == preview["issues"] == []
