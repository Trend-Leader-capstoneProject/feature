"""Frozen E-07/E-09 verification and E-05 coverage mapping.

E-07 reuses existing Preview tests instead of duplicating their inputs:
* test_p01_base_is_ready_but_never_authorized: CONFIRMED/VALID/1, candidate 1.
* test_p03_no_search_is_observed_zero_not_unknown: NOT_CONFIRMED/NOT_EVALUATED/0.
* test_p06_two_completed_searches_reject_before_s0: CONFIRMED/INVALID/2.
* test_p08_broken_output_is_invalid_with_unobserved_calls: UNKNOWN/INVALID/None.
All call assert_preview(): mode=S1_SYNTHETIC (thus never FIXTURE_ONLY), no
simulated_web_search_executed, request/response timestamps None, fixed review
and publication safety, independent_source_verified=False. run_s1() injects
only an in-memory Mock read, asserts one call and no S0 run_preview invocation;
conftest import/I/O guards bound the claim to synthetic execution, not paid API.

E-09: Gate A test_d06_model_metadata_is_not_promoted_into_validated_candidate
already proves raw Parser data vs Validator's three-field candidate. The new
test below independently asserts the actual S1 Preview with poisoned metadata.
Passing candidate validation is not independent verification of source truth.

E-05: run S0 separately with --confcutdir=tests/responses_web_search, without
loading S1 test fixtures. test_contract.api()/run() exercise the public names
SearchRunConfig/FixtureAdapter/run_preview.
test_contract.test_normal_response_and_no_input_mutation checks FIXTURE_ONLY,
simulated execution, safety and input immutability.
test_isolation.test_parent_conftest_and_external_modules_are_not_loaded,
test_forbidden_import_is_blocked_before_module_execution and
test_io_guard_is_active_without_performing_io establish isolated collection,
blocked SDK imports and active DNS/network/process/write/config-read guards.
S0/S1 guards also reject swallowed I/O attempts at teardown; S1's pipeline spy
forbids using S0 run_preview. This covers current fixture contracts, not SDK
compatibility, a complete OS sandbox, or future cross-mode integrations.

E-04c/E-10 output layers and unconnected E-06 DB/Redis/Writer/publication APIs
remain unverified here. Gate C/D, G5/G6 HOLD and P4 NOT FROZEN are unchanged.
"""

from .fixtures import URL, response
from .test_gate_a_followup import base_candidate, set_candidates
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)


def test_e09_model_metadata_is_not_promoted_into_s1_preview(pipeline):
    payload = response()
    raw = base_candidate()
    raw.update(
        publish_authorization="APPROVED",
        review_status="APPROVED",
        publication_status="PUBLISHED",
        independent_source_verified=True,
        source_published_at="2026-11-12T00:00:00Z",
        observed_at="2026-11-12T01:00:00Z",
        collected_at="2026-11-12T02:00:00Z",
        rank=1,
        popularity_score=100,
    )
    set_candidates(payload, [raw])
    preview = run_s1(pipeline, payload=payload)
    assert_flow(pipeline, payload, normalized=True)
    # Confirm poisoned fields really reached the real Parser/Validator boundary.
    parsed = pipeline.validate.call_args.args[0]
    assert parsed.candidates == (raw,)
    assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                   validation="VALID", calls=1)
    assert preview["reason_codes"] == preview["issues"] == []
    assert preview["candidates"] == [{
        "topic_draft": "가상 기기 출시",
        "source_url": URL,
        "source_title_reference": "가상 공식 발표",
        "proposed_category_ref": "IT_DIGITAL",
        "source_published_at": None,
        "review_status": "REVIEW_REQUIRED",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE",
        "independent_source_verified": False,
    }]
    for key in ("rank", "popularity_score", "observed_at", "collected_at"):
        assert key not in preview
