"""Gate A closeout of frozen v0.2.2. AC coverage is not pytest case count.

Existing-test mappings audited against input, result AND forbidden behavior:
* C-01/F-01 -> test_a01_normal_search: unchanged F-BASE has valid JSON and
  matching URL; assert_normalized preserves content/annotations, assert_accepted
  checks real S0 success, exact candidate fields, citation set and no issues.
  No new citation is synthesized. Preview PREVIEW_READY remains Gate B.
* F-02 -> test_c03_sources_cannot_replace_annotations[ F-02 ]: empty annotations,
  no sources. The original C-03 additionally had sources, so one parameter case
  was added. S0 parses successfully then drops the candidate with mismatch;
  normalized content stays empty, distinguishing search from candidate evidence.
* F-03 -> test_c05b_annotation_container_remains_s0_responsibility[missing]:
  valid JSON with missing annotations stays unchanged through normalization;
  S0 returns structure failure, not repaired [] or successful empty candidates.
* X-01 -> test_a04_original_two_calls_cannot_be_hidden plus test_x06: complete
  searches=2 and valid JSON/citation; observed counts stay 2, TOOL_CALL_LIMIT
  rejection, parser_input=None and normalize() spies verify no S0 calls.
* X-02 -> test_a05_failed_tool_is_not_promoted_to_completed: only tool status
  changes to failed; valid JSON/citation remain. REJECTED, completed searches=0,
  parser_input=None and no S0 calls prevent success based on body alone.
* X-04 -> test_b04_two_assistant_messages_cannot_be_selected_or_merged:
  deep-copied F-BASE message makes two individually valid messages/citations;
  observed messages=2, REJECTED/None/no S0 calls disallow selection or merge.
* X-05 -> test_d05_json_error_is_not_empty_success: invalid JSON retains valid
  matching URL citation; text is preserved, S0 returns structure failure with
  zero candidates, and s0() short-circuits without Validator on Parser failure.

New cases below cover D-06/D-08/D-09/F-04 and the Gate A portion of C-07.
All 55 A/B/C/D/F/L/X IDs have their Gate A portions exercised; this is not a
full S1 acceptance declaration. Preview safety/status and execution boundaries
remain Gate B. E-08 and real SDK/offset compatibility remain Gate C/D.

Observed gap: reasoning.summary=[None] was accepted because only list shape is
checked. No frozen nested-summary rejection rule is added or asserted here.
"""

import importlib
import json
from dataclasses import asdict

import pytest

from .fixtures import TEXT, URL, content, response
from .test_gate_a import assert_normalized, normalize, s0
from .test_gate_a_followup import base_candidate, set_candidates


def assert_parser_structure_failure(result, reason="RESPONSE_STRUCTURE_INVALID"):
    parsed, accepted, issues = s0(result)
    assert parsed.status == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert parsed.reason_codes == (reason,)
    assert parsed.candidates == accepted == issues == ()
    validator = importlib.import_module("app.responses_web_search.validator")
    validator.validate_candidates.assert_not_called()


def test_d06_model_metadata_is_not_promoted_into_validated_candidate(monkeypatch):
    payload = response()
    raw = base_candidate()
    raw.update(
        publish_authorization="APPROVED",
        review_status="APPROVED",
        independent_source_verified=True,
        source_published_at="2026-11-12T00:00:00Z",
        observed_at="2026-11-12T00:00:00Z",
        collected_at="2026-11-12T00:00:00Z",
        rank=1,
        popularity_score=100,
    )
    set_candidates(payload, [raw])
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    # Parser preserves model JSON as raw data; Validator exposes only 3 fields.
    assert parsed.candidates == (raw,)
    assert issues == ()
    assert len(accepted) == 1
    assert asdict(accepted[0]) == {
        "topic_draft": "가상 기기 출시", "source_url": URL,
        "source_title_reference": "가상 공식 발표",
    }
    # Final Preview must apply its fixed safety values separately in Gate B.


@pytest.mark.parametrize("candidates", [{}, None], ids=["object", "null"])
def test_d08_candidate_container_is_not_coerced_to_list(candidates, monkeypatch):
    payload = response()
    content(payload)["text"] = json.dumps({"candidates": candidates})
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    assert_parser_structure_failure(result)


@pytest.mark.parametrize("defect", ["missing", "non-list", "missing-url"])
def test_d09_empty_candidates_do_not_bypass_annotation_validation(defect, monkeypatch):
    payload = response()
    content(payload)["text"] = '{"candidates":[]}'
    if defect == "missing":
        del content(payload)["annotations"]
    elif defect == "non-list":
        content(payload)["annotations"] = {}
    else:
        del content(payload)["annotations"][0]["url"]
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    assert_parser_structure_failure(
        result,
        "ANNOTATION_STRUCTURE_INVALID" if defect == "missing-url"
        else "RESPONSE_STRUCTURE_INVALID",
    )


@pytest.mark.parametrize("suffix", [
    "\n합성 추가 설명", " [합성 인용](https://vendor.example.test/releases/1)",
], ids=["explanation", "citation-markup"])
def test_f04_trailing_text_is_not_stripped_or_partially_parsed(suffix, monkeypatch):
    payload = response()
    assert len(json.loads(TEXT)["candidates"]) == 1
    content(payload)["text"] = TEXT + suffix
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    assert result.parser_input["output"][1]["content"][0]["text"] == TEXT + suffix
    assert_parser_structure_failure(result)


def test_c07_url_membership_does_not_establish_semantic_support(monkeypatch):
    payload = response()
    raw = base_candidate()
    raw["topic_draft"] = "합성 기기가 출시되었다"
    set_candidates(payload, [raw])
    # Deliberately contradictory synthetic citation description, not web evidence.
    content(payload)["annotations"][0]["title"] = "합성 출처 설명: 출시 계획이 없다"
    result = normalize(payload, monkeypatch)
    assert_normalized(result, content(payload))
    parsed, accepted, issues = s0(result)
    assert parsed.status is None
    assert parsed.citation_urls == frozenset({URL})
    assert issues == ()
    assert len(accepted) == 1
    assert asdict(accepted[0]) == {
        "topic_draft": "합성 기기가 출시되었다", "source_url": URL,
        "source_title_reference": "가상 공식 발표",
    }
    assert result.citation_trace[0].url == URL
    # Neither this candidate nor the trace certifies truth/semantic support.
    # REVIEW_REQUIRED and independent_source_verified=false are Gate B checks.
