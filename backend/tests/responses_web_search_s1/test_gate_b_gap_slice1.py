"""B-gap Slice 1: eight real S1 inputs close ten AC gaps from frozen v0.2.2.

Search short-circuits: A-03/open_page and A-09/find_in_page.
Normalizer rejection: A-05/A-06/A-07/A-08/B-03/B-04.
X-02 maps to A-05: failed search retains otherwise valid F-BASE JSON/citation.
X-04 maps to B-04: two individually valid F-BASE messages/citations are kept.
These are the same input conditions as the Gate A tests, not extra executions.

Expected counts/search states below are fixed from the original input, never
derived from Normalizer results. In A-06 the top-level response is incomplete
but its intact output still contains one observed completed search; frozen
2.3/P-common preserves that fact independently of response validity.

run_s1 reuses Mock read-once, no S0 FIXTURE_ONLY service and deep-copy checks.
The existing import/I/O guards remain active with zero permitted product I/O
attempts (including swallowed attempts). No new persistence boundary is claimed.
Gate B overall HOLD, Gate C/D unverified, G5/G6 HOLD, P4 NOT FROZEN remain.
"""

import copy
import json

import pytest

from .fixtures import TEXT, URL, content, reasoning, response
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)
from .test_gate_b_preview_remaining import assert_parser_short_circuit


def assert_valid_base_messages(payload, *, count):
    """Independently preserve the valid body beneath the upstream failure."""
    messages = [item for item in payload["output"] if item["type"] == "message"]
    assert len(messages) == count
    for message in messages:
        assert message["content"] == [content(response())]
        candidates = json.loads(message["content"][0]["text"])["candidates"]
        assert candidates == [{
            "topic_draft": "가상 기기 출시", "source_url": URL,
            "source_title_reference": "가상 공식 발표",
        }]
        assert message["content"][0]["annotations"][0]["url"] == URL
        assert message["content"][0]["text"] == TEXT


@pytest.mark.parametrize("action", ["open_page", "find_in_page"], ids=["A-03", "A-09"])
def test_non_search_action_short_circuits_without_fabricating_search(action, pipeline):
    payload = response()
    payload["output"][0]["action"]["type"] = action
    assert_valid_base_messages(payload, count=1)
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=1, searches=0)
    result, = pipeline.normalization_results
    assert result.reason_codes == ()
    assert result.parser_input["output"][0]["action"]["type"] == action
    assert_preview(preview, status="SEARCH_NOT_EXECUTED", search="NOT_CONFIRMED",
                   validation="NOT_EVALUATED", calls=1)
    assert preview["reason_codes"] == []
    assert preview["issues"] == preview["candidates"] == []


@pytest.mark.parametrize("ac,search,searches,messages,response_status", [
    ("A-05", "NOT_CONFIRMED", 0, 1, "completed"),
    ("A-06", "CONFIRMED", 1, 1, "incomplete"),
    ("A-07", "NOT_CONFIRMED", 0, 1, "completed"),
    ("A-08", "CONFIRMED", 1, 1, "completed"),
    ("B-03", "CONFIRMED", 1, 1, "completed"),
    ("B-04", "CONFIRMED", 1, 2, "completed"),
], ids=["A-05-X-02", "A-06", "A-07", "A-08", "B-03", "B-04-X-04"])
def test_normalizer_rejection_short_circuits_real_service(
    ac, search, searches, messages, response_status, pipeline,
):
    payload = response()
    if ac == "A-05":
        payload["output"][0]["status"] = "failed"
    elif ac == "A-06":
        payload["status"] = "incomplete"
    elif ac == "A-07":
        del payload["output"][0]["action"]["type"]
    elif ac == "A-08":
        payload["output"].append({
            "id": "unknown_synthetic_output", "type": "synthetic_unsupported_output",
            "status": "completed",
        })
    elif ac == "B-03":
        auxiliary = reasoning()
        auxiliary["status"] = "incomplete"
        payload["output"].append(auxiliary)
    else:
        second = copy.deepcopy(payload["output"][1])
        second["id"] = "msg_synthetic_second"
        payload["output"].append(second)
    assert_valid_base_messages(payload, count=messages)
    assert sum(item["type"] == "web_search_call" for item in payload["output"]) == 1
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=False)
    result, = pipeline.normalization_results
    assert result.outcome == "REJECTED"
    assert result.parser_input is None
    assert result.execution_evidence.response_status == response_status
    assert result.execution_evidence.web_search_calls_observed == 1
    assert result.execution_evidence.completed_search_actions == searches
    assert result.execution_evidence.assistant_messages_observed == messages
    assert result.reason_codes == ("RESPONSE_STRUCTURE_INVALID",)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE", search=search,
                   validation="INVALID", calls=1)
    assert preview["reason_codes"] == ["RESPONSE_STRUCTURE_INVALID"]
    assert preview["issues"] == preview["candidates"] == []
