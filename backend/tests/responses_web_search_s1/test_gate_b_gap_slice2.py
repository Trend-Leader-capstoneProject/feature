"""B-gap Slice 2: real S1 coverage for B-01/02/05/07/08/09 and C-08.

Reasoning cases use separate projection assertions: assert_flow(normalized=True)
requires unchanged output, whereas normal reasoning must be removed for S0.
Expected evidence and projection are defined from F-BASE before execution.
B-09 also checks final_answer without a search call: phase cannot invent search.
Existing Mock read-once, S0 service non-call, deep-copy and import/I/O guards
are reused without weakening existing assertions or adding product behavior.
Gate B HOLD, Gate C/D unverified, G5/G6 HOLD, P4 NOT FROZEN remain unchanged.
"""

import copy

import pytest

from .fixtures import URL, content, reasoning, response
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)
from .test_gate_b_preview_remaining import assert_parser_short_circuit


def assert_ready(preview):
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["reason_codes"] == preview["issues"] == []
    assert preview["candidates"] == [{
        "topic_draft": "가상 기기 출시", "source_url": URL,
        "source_title_reference": "가상 공식 발표",
        "proposed_category_ref": "IT_DIGITAL", "source_published_at": None,
        "review_status": "REVIEW_REQUIRED",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE", "independent_source_verified": False,
    }]


@pytest.mark.parametrize("status", ["completed", None], ids=["B-01", "B-02"])
def test_reasoning_is_validated_then_excluded_from_real_parser_input(status, pipeline):
    payload = response()
    expected_output = copy.deepcopy(payload["output"])
    auxiliary = reasoning()
    if status is None:
        del auxiliary["status"]
    expected_reasoning = copy.deepcopy(auxiliary)
    payload["output"].append(auxiliary)
    preview = run_s1(pipeline, payload=payload)
    pipeline.normalize.assert_called_once_with(payload, pipeline.config)
    result, = pipeline.normalization_results
    assert result.outcome == "NORMALIZED"
    assert result.reason_codes == ()
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == 1
    projected = result.parser_input
    pipeline.parse.assert_called_once_with(projected, pipeline.config)
    assert pipeline.parse.call_args.args[0] is projected
    assert projected["status"] == "completed"
    assert projected["output"] == expected_output
    assert [item["type"] for item in projected["output"]] == [
        "web_search_call", "message",
    ]
    assert payload["output"][2] == expected_reasoning
    if status is None:
        assert "status" not in payload["output"][2]
    pipeline.validate.assert_called_once()
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.status is None
    assert parsed.tool_calls_observed == 1
    assert parsed.citation_urls == frozenset({URL})
    assert [event[0] for event in pipeline.events.mock_calls] == [
        "read", "normalize", "parse", "validate",
    ]
    assert_ready(preview)


@pytest.mark.parametrize(
    "phase", [None, "final_answer"], ids=["absent", "final_answer"],
)
def test_b09_optional_phase_preserves_real_search_evidence(phase, pipeline):
    payload = response()
    if phase is not None:
        payload["output"][1]["phase"] = phase
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    result, = pipeline.normalization_results
    assert result.outcome == "NORMALIZED"
    assert result.reason_codes == ()
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == 1
    message = result.parser_input["output"][1]
    if phase is None:
        assert "phase" not in payload["output"][1]
        assert "phase" not in message
    else:
        assert message["phase"] == "final_answer"
    assert_ready(preview)


def test_b09_final_phase_does_not_replace_missing_search_evidence(pipeline):
    payload = response()
    payload["output"][1]["phase"] = "final_answer"
    payload["output"].pop(0)
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=0, searches=0)
    assert_preview(preview, status="SEARCH_NOT_EXECUTED", search="NOT_CONFIRMED",
                   validation="NOT_EVALUATED", calls=0)
    assert preview["reason_codes"] == preview["issues"] == preview["candidates"] == []


@pytest.mark.parametrize("ac,messages", [
    ("B-05", 1), ("B-07", 0), ("B-08", 1), ("C-08", 1),
], ids=["B-05", "B-07", "B-08", "C-08"])
def test_ambiguous_or_unsupported_content_rejects_before_s0(ac, messages, pipeline):
    payload = response()
    if ac == "B-05":
        payload["output"][1]["content"].append(copy.deepcopy(content(payload)))
        assert payload["output"][1]["content"] == [
            content(response()), content(response()),
        ]
    elif ac == "B-07":
        payload["output"].pop(1)
        assert [item["type"] for item in payload["output"]] == ["web_search_call"]
    elif ac == "B-08":
        payload["output"][1]["content"].append({
            "type": "synthetic_unsupported_content",
        })
        assert content(payload) == content(response())
    else:
        content(payload)["annotations"].append({
            "type": "synthetic_unsupported_annotation",
        })
        assert content(payload)["annotations"][0] == (
            content(response())["annotations"][0]
        )
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=False)
    result, = pipeline.normalization_results
    assert result.outcome == "REJECTED"
    assert result.parser_input is None
    assert result.execution_evidence.response_status == "completed"
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == messages
    assert result.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=1)
    assert preview["reason_codes"] == ["RESPONSE_STRUCTURE_INVALID"]
    assert preview["issues"] == preview["candidates"] == []
