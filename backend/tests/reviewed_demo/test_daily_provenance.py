"""New citation provenance and old receipts, using the existing SQLite fixture."""

from unittest.mock import MagicMock

import pytest
from test_daily_registration import batch_for, isolated_sqlite as isolated_sqlite

from app.services import reviewed_demo_daily_registration as daily


def matched_batch(citation="MATCHED"):
    from app.responses_web_search.draft_export import build_reviewed_draft

    preview = {
        "mode": "LIVE", "search_profile": "IT_DIGITAL", "status": "PREVIEW_READY",
        "search_execution": "CONFIRMED", "response_validation": "PARTIAL",
        "citation_validation": "PARTIAL", "candidate_validation": "VALID",
        "candidates": [{
            "candidate_index": 2, "citation_validation": "MATCHED",
            "proposed_category_ref": "IT_DIGITAL", "topic_draft": "합성 후보",
            "source_url": "https://example.org/original-source",
            "source_title_reference": "합성 출처 제목",
        }], "review_only_candidates": [], "issues": [], "reason_codes": [],
    }
    if citation == "MISMATCH":
        item = preview["candidates"].pop()
        item.update(
            citation_validation="MISMATCH", rejection_reason="CITATION_URL_MISMATCH",
        )
        preview.update(
            review_only_candidates=[item], status="NO_VALID_CANDIDATES",
            candidate_validation="INVALID", citation_validation="MISMATCH",
        )
    data = build_reviewed_draft(preview, profile="IT_DIGITAL", run_id="a" * 32)
    data.update(reviewer_alias="synthetic-reviewer", approved_record_count=1)
    reviewed = batch_for()["records"][0]
    data["records"][0].update({
        key: reviewed[key] for key in (
            "title", "source_title", "source_url", "child_name", "review_note",
            "source_review", "operator_approved",
        )
    })
    return data


def legacy_batch(status, failure):
    data = batch_for()
    data["records"][0].update(
        discovery_method="OPENAI_RESPONSES_WEB_SEARCH_LIVE", original_failure=failure,
        original_ai_source_url="https://example.org/original-source",
    )
    if status is not None:
        data["records"][0]["original_citation_validation"] = status
    return data


@pytest.mark.parametrize("status,failure", [
    ("MATCHED", None), ("MISMATCH", "CITATION_URL_MISMATCH"),
    ("NOT_EVALUATED", "NOT_VALIDATED"),
    (None, "CITATION_URL_MISMATCH"), (None, "NOT_VALIDATED"),
])
def test_old_and_new_provenance_validate(status, failure):
    data = matched_batch() if status == "MATCHED" else legacy_batch(status, failure)
    assert len(daily.validate_batch(data)) == 1


@pytest.mark.parametrize("change", [
    {"original_failure": "NOT_VALIDATED"},
    {"original_citation_validation": "PASS"},
    {"original_citation_validation": "MISMATCH"},
    {"candidate_index": True}, {"candidate_index": 3},
    {"search_evidence_sha256": "invented"}, {"search_run_id": "invented"},
    {"search_profile": "OTHER"},
])
def test_provenance_inconsistency_blocks_before_connection(change):
    data = matched_batch()
    data["records"][0].update(change)
    engine = MagicMock()
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.preflight_batch(engine, data)
    engine.connect.assert_not_called()


@pytest.mark.parametrize("citation", ["MATCHED", "MISMATCH"])
def test_success_receipt_keeps_new_provenance(isolated_sqlite, citation):
    engine, _ = isolated_sqlite
    data = matched_batch(citation)
    assert daily.preflight_batch(engine, data)["status"] == "DRY_RUN_READY"
    receipt = daily.register_candidate(engine, daily.validate_batch(data)[0])
    for key in (
        "original_ai_source_url", "original_failure", "original_citation_validation",
        "original_response_citation_validation", "original_response_validation",
        "search_profile", "candidate_index", "search_run_id", "search_evidence_sha256",
    ):
        assert receipt[key] == data["records"][0][key]
    assert receipt["original_ai_source_url"] != data["records"][0]["source_url"]


@pytest.mark.parametrize("failure", ["CITATION_URL_MISMATCH", "NOT_VALIDATED"])
def test_legacy_receipt_keeps_original_failure(isolated_sqlite, failure):
    engine, _ = isolated_sqlite
    data = legacy_batch(None, failure)
    receipt = daily.register_candidate(engine, daily.validate_batch(data)[0])
    assert receipt["original_failure"] == failure
    assert "original_citation_validation" not in receipt


@pytest.mark.parametrize("change", [
    lambda b: b.pop("search_runs"),
    lambda b: b["search_runs"][0]["evidence"].update(citation_validation="MATCHED"),
    lambda b: b["records"][0].update(original_ai_source_url="https://example.org/changed"),
    lambda b: b["records"][0].update(search_profile="FASHION"),
    lambda b: b["records"][0].update(candidate_index=0),
])
def test_provenance_must_reference_unchanged_retained_evidence(change):
    data = matched_batch()
    change(data)
    engine = MagicMock()
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.preflight_batch(engine, data)
    engine.connect.assert_not_called()


def test_valid_other_category_cannot_replace_search_category(
    isolated_sqlite, monkeypatch,
):
    engine, metadata = isolated_sqlite
    data = matched_batch()
    record = data["records"][0]
    record.update(parent_code="FASHION", child_name="신발")
    with engine.begin() as connection:
        connection.execute(metadata.tables["categories"].insert(), [
            {"category_id": 90, "category_name": "패션", "category_code": "FASHION",
             "parent_id": None, "is_active": True, "sort_order": 1},
            {"category_id": 91, "category_name": "신발", "category_code": None,
             "parent_id": 90, "is_active": True, "sort_order": 2},
        ])
        candidate = daily.Candidate(1, None, None, record)
        assert daily._category_id(connection, candidate) == 91
    connect = MagicMock()
    monkeypatch.setattr(engine, "connect", connect)
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.preflight_batch(engine, data)
    connect.assert_not_called()


@pytest.mark.parametrize("missing", [
    ("search_run_id",), ("search_evidence_sha256",), ("candidate_index",),
    ("search_run_id", "search_evidence_sha256", "candidate_index"),
])
def test_matched_requires_complete_evidence_reference(missing):
    data = matched_batch()
    for key in missing:
        data["records"][0].pop(key)
    engine = MagicMock()
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.preflight_batch(engine, data)
    engine.connect.assert_not_called()


def test_matched_cannot_reference_a_mismatch_candidate():
    data = matched_batch("MISMATCH")
    data["records"][0].update(
        original_citation_validation="MATCHED", original_failure=None,
    )
    engine = MagicMock()
    with pytest.raises(daily.RegistrationBlocked, match="PROVENANCE_MISMATCH"):
        daily.preflight_batch(engine, data)
    engine.connect.assert_not_called()


@pytest.mark.parametrize("stage", ["untouched", "count-only", "review-only"])
def test_exported_draft_is_blocked_even_before_database_inspection(stage):
    from app.responses_web_search.draft_export import build_reviewed_draft

    preview = {
        "mode": "LIVE", "search_profile": "IT_DIGITAL", "status": "PREVIEW_READY",
        "search_execution": "CONFIRMED", "response_validation": "VALID",
        "citation_validation": "MATCHED", "candidate_validation": "VALID",
        "candidates": [{
            "candidate_index": 0, "citation_validation": "MATCHED",
            "proposed_category_ref": "IT_DIGITAL", "topic_draft": "합성 후보",
            "source_url": "https://example.org/test",
            "source_title_reference": "합성 출처 제목",
        }], "review_only_candidates": [], "issues": [], "reason_codes": [],
    }
    batch = build_reviewed_draft(preview, profile="IT_DIGITAL", run_id="a" * 32)
    if stage == "count-only":
        batch.update(reviewer_alias="synthetic-reviewer", approved_record_count=1)
    elif stage == "review-only":
        batch.update(reviewer_alias="synthetic-reviewer", approved_record_count=1)
        batch["records"][0].update(
            child_name="인공지능", review_note="합성 검토 메모",
            source_review=daily.REVIEW_CHECK,
        )
    engine = MagicMock()
    with pytest.raises(daily.RegistrationBlocked):
        daily.preflight_batch(engine, batch)
    engine.connect.assert_not_called()
