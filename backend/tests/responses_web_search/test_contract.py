"""Red specification. All product imports happen in test calls, not collection.

The public names below are the S0 project contract, not OpenAI SDK methods.
"""

import copy
import importlib
import json
from datetime import datetime, timezone

import pytest

from .fixtures import candidate, response


def api():
    # An absent app.responses_web_search is the intended initial Red failure.
    return importlib.import_module("app.responses_web_search")


def run(payload):
    module = api()
    return module.run_preview(
        config=module.SearchRunConfig(),
        adapter=module.FixtureAdapter(response=payload),
    )


def content(payload):
    return payload["output"][-1]["content"][0]


def assert_safety(preview):
    assert preview["mode"] == "FIXTURE_ONLY"
    assert preview["review_status"] == "REVIEW_REQUIRED"
    assert preview["publication_status"] == "NOT_FOR_PUBLICATION"
    assert preview["publish_authorization"] == "NONE"
    assert preview["independent_source_verified"] is False
    assert preview["searched_at_utc"] is None
    assert "observed_at" not in preview
    assert "collected_at" not in preview
    assert "rank" not in preview
    assert "popularity_score" not in preview
    for item in preview["candidates"]:
        assert item["review_status"] == "REVIEW_REQUIRED"
        assert item["publication_status"] == "NOT_FOR_PUBLICATION"
        assert item["publish_authorization"] == "NONE"
        assert item["independent_source_verified"] is False
        assert item["source_published_at"] is None
        assert item["proposed_category_ref"] == "IT_DIGITAL"
        assert "observed_at" not in item
        assert "collected_at" not in item
        assert "rank" not in item
        assert "popularity_score" not in item


def test_normal_response_and_no_input_mutation(isolated_session):
    payload = response()
    original = copy.deepcopy(payload)
    preview = run(payload)
    assert preview["status"] == "PREVIEW_READY"
    assert preview["simulated_web_search_executed"] is True
    assert preview["tool_calls_observed"] == 1
    assert preview["issues"] == []
    assert len(preview["candidates"]) == 1
    assert preview["candidates"][0]["topic_draft"] == "가상 기기 출시"
    assert payload == original
    assert_safety(preview)


def test_three_candidates_are_allowed():
    preview = run(response([
        candidate(f"가상 주제 {i}", f"https://vendor.example.test/{i}")
        for i in range(3)
    ]))
    assert len(preview["candidates"]) == 3
    assert_safety(preview)


@pytest.mark.parametrize("profile,days,limit,calls", [
    ("OTHER", 7, 3, 1), ("IT_DIGITAL", 8, 3, 1),
    ("IT_DIGITAL", 7, 4, 1), ("IT_DIGITAL", 7, 0, 1),
    ("IT_DIGITAL", 7, 3, 2), ("IT_DIGITAL", 7, True, 1),
])
def test_invalid_configuration_is_rejected(profile, days, limit, calls):
    module = api()
    with pytest.raises(ValueError):
        module.SearchRunConfig(
            profile=profile, lookback_days=days,
            max_candidates=limit, max_tool_calls=calls,
        )


def test_fixed_fixture_clock_is_not_a_real_search_timestamp():
    module = api()
    anchor = datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc)
    preview = module.run_preview(
        config=module.SearchRunConfig(fixture_reference_at_utc=anchor),
        adapter=module.FixtureAdapter(response=response()),
    )
    assert preview["fixture_reference_at_utc"] == anchor.isoformat()
    assert preview["lookback_days"] == 7
    assert_safety(preview)


def test_missing_search_is_not_success_even_with_citation():
    payload = response()
    payload["output"] = payload["output"][1:]
    preview = run(payload)
    assert preview["status"] == "SEARCH_NOT_EXECUTED"
    assert preview["candidates"] == []
    assert preview["simulated_web_search_executed"] is False
    assert_safety(preview)


def test_open_page_is_not_a_search():
    payload = response()
    payload["output"][0]["action"] = {
        "type": "open_page", "url": "https://vendor.example.test/",
    }
    assert run(payload)["status"] == "SEARCH_NOT_EXECUTED"


@pytest.mark.parametrize("target", ["response", "tool", "message"])
def test_incomplete_status_fails_closed(target):
    payload = response()
    item = payload if target == "response" else payload["output"][
        0 if target == "tool" else 1
    ]
    item["status"] = "incomplete"
    preview = run(payload)
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert_safety(preview)


def test_refusal_anywhere_prevents_partial_preview():
    payload = response()
    payload["output"][-1]["content"].append({
        "type": "refusal", "refusal": "合成拒否_SECRET_DO_NOT_LOG",
    })
    preview = run(payload)
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert "SECRET_DO_NOT_LOG" not in json.dumps(preview)
    assert_safety(preview)


def test_tool_limit_counts_all_observed_calls():
    payload = response()
    payload["output"].insert(0, copy.deepcopy(payload["output"][0]))
    preview = run(payload)
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert "TOOL_CALL_LIMIT_EXCEEDED" in preview["reason_codes"]


@pytest.mark.parametrize("malformation", [
    "not_object", "missing_output", "output_not_list", "missing_content",
    "invalid_json", "candidates_not_list", "candidate_not_object",
    "unknown_content", "multiple_text_blocks",
])
def test_malformed_response_has_no_partial_candidates(malformation):
    payload = response()
    if malformation == "not_object":
        payload = []
    elif malformation == "missing_output":
        del payload["output"]
    elif malformation == "output_not_list":
        payload["output"] = {}
    elif malformation == "missing_content":
        del payload["output"][-1]["content"]
    elif malformation == "invalid_json":
        content(payload)["text"] = "not json SECRET_DO_NOT_LOG"
    elif malformation == "candidates_not_list":
        content(payload)["text"] = '{"candidates": {}}'
    elif malformation == "candidate_not_object":
        content(payload)["text"] = '{"candidates": [null]}'
    elif malformation == "unknown_content":
        content(payload)["type"] = "unknown_content"
    else:
        payload["output"][-1]["content"].append(copy.deepcopy(content(payload)))
    preview = run(payload)
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert "SECRET_DO_NOT_LOG" not in json.dumps(preview)
    assert_safety(preview)


@pytest.mark.parametrize("kind", ["missing", "mismatch", "sources_only"])
def test_candidate_needs_matching_citation_not_just_sources(kind):
    payload = response()
    if kind == "mismatch":
        content(payload)["annotations"][0]["url"] = "https://other.example.test/"
    else:
        content(payload)["annotations"] = []
    if kind == "sources_only":
        payload["output"][0]["action"]["sources"] = [{
            "type": "url", "url": candidate()["source_url"],
        }]
    preview = run(payload)
    assert preview["status"] == "NO_VALID_CANDIDATES"
    assert preview["candidates"] == []
    assert preview["issues"] == [{"candidate_index": 0,
                                  "code": "CITATION_URL_MISMATCH"}]
    assert_safety(preview)


@pytest.mark.parametrize("url", [
    "relative/path", "javascript:alert(1)", "file:///C:/private",
    "https://user:pass@vendor.example.test/", "http://localhost/",
    "http://127.0.0.1/", "http://[::1]/", "http://2130706433/",
    "https://vendor.example.test:444/", "https://vendor.example.test:/",
    "https://vendor.example.test/a\nb", "https://vendor.example.test/\\x",
    "https://%76endor.example.test/", "https://vendor.example.test./",
])
def test_invalid_url_is_excluded_without_fetching(url):
    preview = run(response([candidate(url=url)]))
    assert preview["status"] == "NO_VALID_CANDIDATES"
    assert preview["candidates"] == []
    assert preview["issues"] == [{"candidate_index": 0,
                                  "code": "SOURCE_URL_INVALID"}]
    assert_safety(preview)


@pytest.mark.parametrize("field", ["source_url", "source_title_reference",
                                   "topic_draft"])
def test_missing_required_candidate_field_is_excluded(field):
    item = candidate()
    del item[field]
    preview = run(response([item]))
    assert preview["status"] == "NO_VALID_CANDIDATES"
    assert preview["issues"] == [{"candidate_index": 0,
                                  "code": "CANDIDATE_FIELDS_INVALID"}]


def test_mixed_candidates_keep_valid_one_with_diagnostic():
    preview = run(response([
        candidate(), candidate("별도 주제", "file:///private"),
    ]))
    assert preview["status"] == "PREVIEW_READY"
    assert len(preview["candidates"]) == 1
    assert preview["issues"] == [{"candidate_index": 1,
                                  "code": "SOURCE_URL_INVALID"}]
    assert_safety(preview)


@pytest.mark.parametrize("kind", ["url", "topic"])
def test_duplicate_first_valid_candidate_wins(kind):
    first = candidate("가상 DEVICE", "https://vendor.example.test/a#first")
    second = candidate("다른 주제", "https://VENDOR.example.test:443/a#second")
    if kind == "topic":
        second = candidate("  가상   device  ", "https://other.example.test/a")
    preview = run(response([first, second]))
    assert preview["status"] == "PREVIEW_READY"
    assert len(preview["candidates"]) == 1
    assert preview["candidates"][0]["topic_draft"] == first["topic_draft"]
    assert preview["issues"] == [{"candidate_index": 1,
                                  "code": "DUPLICATE_CANDIDATE"}]


def test_over_limit_is_rejected_instead_of_truncated():
    preview = run(response([
        candidate(f"주제 {i}", f"https://vendor.example.test/{i}")
        for i in range(4)
    ]))
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert "CANDIDATE_LIMIT_EXCEEDED" in preview["reason_codes"]


def test_normal_empty_result_is_distinct_from_all_rejected():
    empty = run(response([]))
    rejected = run(response([candidate(url="file:///private")]))
    assert empty["status"] == "EMPTY_RESULT"
    assert empty["issues"] == []
    assert empty["simulated_web_search_executed"] is True
    assert rejected["status"] == "NO_VALID_CANDIDATES"
    assert len(rejected["issues"]) == 1
    assert_safety(empty)
    assert_safety(rejected)


@pytest.mark.parametrize("kind", ["401", "403", "429", "5xx", "timeout"])
def test_synthetic_adapter_error_has_no_retry(kind):
    module = api()
    adapter = module.FixtureAdapter(error_kind=kind)
    preview = module.run_preview(config=module.SearchRunConfig(), adapter=adapter)
    assert preview["status"] == "UPSTREAM_ERROR"
    assert preview["reason_codes"] == [kind]
    assert preview["candidates"] == []
    assert adapter.calls == 1
    assert_safety(preview)


def test_untrusted_fields_cannot_authorize_or_forge_dates():
    item = candidate()
    item.update({
        "publish_authorization": "APPROVED", "review_status": "G4_APPROVED",
        "source_published_at": "2026-11-12T00:00:00Z",
        "observed_at": "2026-11-12T00:00:00Z", "rank": 1,
        "popularity_score": 100, "independent_source_verified": True,
    })
    preview = run(response([item]))
    assert preview["status"] == "PREVIEW_READY"
    assert_safety(preview)


def test_fixture_adapter_reads_exactly_once():
    module = api()
    adapter = module.FixtureAdapter(response=response())
    module.run_preview(config=module.SearchRunConfig(), adapter=adapter)
    assert adapter.calls == 1


@pytest.mark.parametrize("field", [
    "topic_draft", "source_url", "source_title_reference",
])
@pytest.mark.parametrize("value", [None, "", " \t\n", 42, False, True])
def test_r01_required_fields_reject_invalid_values(field, value):
    item = candidate()
    item[field] = value
    # Keep annotation structure valid: R-01 changes only the candidate field.
    payload = response()
    content(payload)["text"] = json.dumps({"candidates": [item]})
    preview = run(payload)
    assert preview["status"] == "NO_VALID_CANDIDATES"
    assert preview["candidates"] == []
    assert preview["issues"] == [{
        "candidate_index": 0, "code": "CANDIDATE_FIELDS_INVALID",
    }]
    assert_safety(preview)


@pytest.mark.parametrize("annotations", [
    None, {}, "invalid", [None], [42], [{}],
    [{"type": "url_citation"}],
    [{"type": "url_citation", "url": None}],
    [{"type": "url_citation", "url": 42}],
    [{"type": "url_citation", "url": False}],
    [{"type": "url_citation", "url": ""}],
    [{"type": "url_citation", "url": "  "}],
    [{"type": "unknown", "url": candidate()["source_url"]}],
])
@pytest.mark.parametrize("mixed", [False, True])
def test_r02_malformed_annotations_fail_closed_even_with_valid_citation(
    annotations, mixed,
):
    payload = response()
    if mixed and isinstance(annotations, list):
        annotations = content(payload)["annotations"] + annotations
    content(payload)["annotations"] = annotations
    preview = run(payload)
    assert preview["status"] == "INVALID_OR_INCOMPLETE_RESPONSE"
    assert preview["candidates"] == []
    assert_safety(preview)


def test_r02_valid_and_nonmatching_string_citations_can_coexist():
    payload = response()
    content(payload)["annotations"].append({
        "type": "url_citation", "url": "https://other.example.test/",
    })
    preview = run(payload)
    assert preview["status"] == "PREVIEW_READY"
    assert len(preview["candidates"]) == 1
    assert_safety(preview)
