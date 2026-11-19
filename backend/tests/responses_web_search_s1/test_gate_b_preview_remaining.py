"""Gate B Red Phase 2: frozen v0.2.2 P-03/P-04/P-06.

Reuse Phase 1's real pipeline spies, Mock read boundary, Preview safety checks
and input immutability check. These cases may already pass; no forced Red.
Parser short-circuit paths need their own assertions because assert_flow's
normalized=True branch requires Validator success. E-02 is intentionally not
bound to an exception type here: its Mock failure contract awaits a decision.
Gate C/D, G5/G6 HOLD and P4 NOT FROZEN remain unchanged.
"""

import copy

from .fixtures import content, response
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)


def assert_parser_short_circuit(pipeline, payload, *, calls, searches):
    pipeline.normalize.assert_called_once_with(payload, pipeline.config)
    result, = pipeline.normalization_results
    assert result.outcome == "NORMALIZED"
    assert result.execution_evidence.web_search_calls_observed == calls
    assert result.execution_evidence.completed_search_actions == searches
    pipeline.parse.assert_called_once_with(result.parser_input, pipeline.config)
    assert pipeline.parse.call_args.args[0] is result.parser_input
    assert result.parser_input["status"] == payload["status"]
    assert result.parser_input["output"] == payload["output"]
    pipeline.validate.assert_not_called()
    assert [event[0] for event in pipeline.events.mock_calls] == [
        "read", "normalize", "parse",
    ]


def test_p03_no_search_is_observed_zero_not_unknown(pipeline):
    payload = response()
    payload["output"].pop(0)
    assert not any(item["type"] == "web_search_call" for item in payload["output"])
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=0, searches=0)
    assert_preview(preview, status="SEARCH_NOT_EXECUTED", search="NOT_CONFIRMED",
                   validation="NOT_EVALUATED", calls=0)
    # assert_preview enforces type int for zero; P-02/P-08 separately require None.
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == []


def test_p04_bad_json_keeps_completed_search_evidence(pipeline):
    payload = response()
    content(payload)["text"] = '{"candidates":['
    preview = run_s1(pipeline, payload=payload)
    assert_parser_short_circuit(pipeline, payload, calls=1, searches=1)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=1)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == ["RESPONSE_STRUCTURE_INVALID"]


def test_p06_two_completed_searches_reject_before_s0(pipeline):
    payload = response()
    second = copy.deepcopy(payload["output"][0])
    second["id"] = "ws_synthetic_second"
    payload["output"].append(second)
    assert sum(item["type"] == "web_search_call" for item in payload["output"]) == 2
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=False)
    result, = pipeline.normalization_results
    assert result.outcome == "REJECTED"
    assert result.parser_input is None
    assert result.execution_evidence.web_search_calls_observed == 2
    assert result.execution_evidence.completed_search_actions == 2
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=2)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == ["TOOL_CALL_LIMIT_EXCEEDED"]
