"""B-gap Slice 5: frozen L-01..L-06 exercised through the real S1 Service.

Limits and expectations are independent constants from frozen 2.5/5.L.
Reasoning removal is checked separately from unchanged-output assert_flow.
Mock read-once, no S0 service, original deep-copy and import/I/O guards remain.
Closing L gaps does not close E-04c/E-06/E-10's unverified external boundaries.
Gate B HOLD, Gate C/D unverified, G5/G6 HOLD, P4 NOT FROZEN remain unchanged.
"""

import copy
import json

import pytest

from .fixtures import URL, content, padded_response, reasoning, response
from .test_gate_b_gap_slice2 import assert_ready
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)


def assert_boundary_result(pipeline, payload, *, reason=None, expected_output=None):
    preview = run_s1(pipeline, payload=payload)
    pipeline.normalize.assert_called_once_with(payload, pipeline.config)
    result, = pipeline.normalization_results
    assert result.execution_evidence.response_status == "completed"
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == 1
    assert result.execution_evidence.assistant_messages_observed == 1
    if reason is not None:
        assert_flow(pipeline, payload, normalized=False)
        assert result.outcome == "REJECTED"
        assert result.parser_input is None
        assert result.reason_codes == (reason,)
        assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                       search="CONFIRMED", validation="INVALID", calls=1)
        assert preview["reason_codes"] == [reason]
        assert preview["issues"] == preview["candidates"] == []
        return result
    assert result.outcome == "NORMALIZED"
    assert result.reason_codes == ()
    if expected_output is None:
        assert_flow(pipeline, payload, normalized=True)
    else:
        pipeline.parse.assert_called_once_with(result.parser_input, pipeline.config)
        assert pipeline.parse.call_args.args[0] is result.parser_input
        assert result.parser_input["status"] == "completed"
        assert result.parser_input["output"] == expected_output
        assert [item["type"] for item in result.parser_input["output"]] == [
            "web_search_call", "message",
        ]
        pipeline.validate.assert_called_once()
        assert [event[0] for event in pipeline.events.mock_calls] == [
            "read", "normalize", "parse", "validate",
        ]
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.status is None
    assert parsed.tool_calls_observed == 1
    assert parsed.citation_urls == frozenset({URL})
    assert_ready(preview)
    return result


@pytest.mark.parametrize("size,reason", [
    (32768, None), (32769, "S1_TEXT_BYTES_LIMIT_EXCEEDED"),
], ids=["L-01", "L-02"])
def test_utf8_byte_limit_preserves_json_and_search_evidence(size, reason, pipeline):
    payload = padded_response(size)
    text = content(payload)["text"]
    assert len(text.encode("utf-8")) == size
    assert len(text) < 32768
    assert "한" in text
    assert json.loads(text)["candidates"] == [{
        "topic_draft": "가상 기기 출시", "source_url": URL,
        "source_title_reference": "가상 공식 발표",
    }]
    assert content(payload)["annotations"] == content(response())["annotations"]
    assert text[55:93] == URL
    assert_boundary_result(pipeline, payload, reason=reason)


@pytest.mark.parametrize("count,reason", [
    (16, None), (17, "S1_OUTPUT_ITEMS_LIMIT_EXCEEDED"),
], ids=["L-03", "L-04"])
def test_original_output_limit_precedes_reasoning_projection(count, reason, pipeline):
    payload = response()
    expected_output = copy.deepcopy(payload["output"])
    auxiliary = [reasoning(index) for index in range(count - 2)]
    payload["output"].extend(auxiliary)
    assert len(payload["output"]) == count
    assert len(auxiliary) == (14 if count == 16 else 15)
    assert all(item["status"] == "completed" and item["summary"] == []
               and item["type"] == "reasoning" and item["id"] for item in auxiliary)
    assert_boundary_result(pipeline, payload, reason=reason,
                           expected_output=expected_output)


@pytest.mark.parametrize("count,reason", [
    (32, None), (33, "S1_ANNOTATIONS_LIMIT_EXCEEDED"),
], ids=["L-05", "L-06"])
def test_annotation_limit_does_not_deduplicate_or_truncate(count, reason, pipeline):
    payload = response()
    annotation = copy.deepcopy(content(payload)["annotations"][0])
    content(payload)["annotations"] = [copy.deepcopy(annotation) for _ in range(count)]
    assert len(content(payload)["annotations"]) == count
    assert all(item == annotation for item in content(payload)["annotations"])
    result = assert_boundary_result(pipeline, payload, reason=reason)
    if reason is None:
        assert len(result.citation_trace) == 32
        assert [
            (trace.output_index, trace.content_index, trace.annotation_index,
             trace.url, trace.start_index, trace.end_index)
            for trace in result.citation_trace
        ] == [(1, 0, index, URL, 55, 93) for index in range(32)]
        # 32 original traces versus the Validator's one-element URL set above.
