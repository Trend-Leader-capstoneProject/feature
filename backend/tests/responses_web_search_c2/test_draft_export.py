"""Draft persistence uses synthetic data and external temporary directories only."""

import hashlib
import importlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import httpx2
import pytest
from d1_support import INSTANT, PHRASE, Terminal
from support import API_KEY
from test_mvp_preview import payload_for

RUN_ID = "a" * 32


def product():
    return importlib.import_module("app.responses_web_search.draft_export")


@pytest.fixture
def preview():
    return {
        "mode": "LIVE", "search_profile": "FASHION", "status": "PREVIEW_READY",
        "search_execution": "CONFIRMED", "response_validation": "VALID",
        "citation_validation": "PARTIAL", "candidate_validation": "PARTIAL",
        "request_started_at_utc": "2031-01-02T03:00:00+00:00",
        "response_received_at_utc": "2031-01-02T03:00:02+00:00",
        "reason_codes": [], "issues": [
            {"candidate_index": 0, "code": "CITATION_URL_MISMATCH"},
        ],
        "candidates": [{
            "candidate_index": 2, "citation_validation": "MATCHED",
            "proposed_category_ref": "FASHION", "topic_draft": "합성 패션 후보",
            "source_url": "https://example.org/fashion/matched",
            "source_title_reference": "합성 원문 제목",
        }],
        "review_only_candidates": [{
            "candidate_index": 0, "citation_validation": "MISMATCH",
            "proposed_category_ref": "FASHION", "topic_draft": "합성 검토 후보",
            "source_url": "https://example.org/fashion/mismatch",
            "source_title_reference": "검토용 원문 제목",
            "rejection_reason": "CITATION_URL_MISMATCH",
        }],
    }


@pytest.mark.parametrize("profile", [
    "FASHION", "BEAUTY", "GAME", "FOOD", "ENTERTAINMENT", "IT_DIGITAL",
])
def test_draft_keeps_original_indices_and_never_approves(preview, profile):
    preview["search_profile"] = profile
    for item in preview["candidates"] + preview["review_only_candidates"]:
        item["proposed_category_ref"] = profile
    original = deepcopy(preview)
    batch = product().build_reviewed_draft(preview, profile=profile, run_id=RUN_ID)
    assert batch["approved_record_count"] == 0
    assert batch["reviewer_alias"] is None
    assert [item["candidate_index"] for item in batch["records"]] == [0, 2]
    for record in batch["records"]:
        assert record["parent_code"] == profile
        assert record["search_profile"] == profile
        assert record["child_name"] is None
        assert record["operator_approved"] is False
        assert record["source_review"] == "NOT_REVIEWED"
        assert record["original_ai_source_url"] == record["source_url"]
        assert record["original_response_citation_validation"] == "PARTIAL"
    assert batch["records"][0]["original_failure"] == "CITATION_URL_MISMATCH"
    assert batch["records"][1]["original_failure"] is None
    assert preview == original


def test_hash_is_of_the_actual_whitelisted_evidence(preview):
    preview["raw_response"] = API_KEY
    preview["candidates"][0]["password"] = API_KEY
    batch = product().build_reviewed_draft(preview, profile="FASHION", run_id=RUN_ID)
    run, = batch["search_runs"]
    encoded = json.dumps(run["evidence"], ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert run["search_evidence_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert run["search_run_id"] == RUN_ID
    assert API_KEY not in json.dumps(batch)
    for record in batch["records"]:
        assert record["search_evidence_sha256"] == run["search_evidence_sha256"]


@pytest.mark.parametrize("bad", [
    API_KEY, "password=synthetic-db-password", "Bearer synthetic-secret",
    "https://user:password@example.org/source", "hidden\u200btext",
    "https://example.org/?api_key%3Dprivate-value",
    "https://example.org/?access_token=private-value", "db_password=private-value",
])
def test_sensitive_candidate_content_is_not_persisted(preview, tmp_path, bad):
    preview["candidates"][0]["source_title_reference"] = bad
    with product().reserve_draft(tmp_path) as target:
        with pytest.raises(product().DraftExportError):
            target.save(preview, profile="FASHION", private_texts=(API_KEY,))
        assert target.path.read_bytes() == b""


@pytest.mark.parametrize("change", [
    lambda p: p.update(search_profile="GAME"),
    lambda p: p["candidates"][0].update(candidate_index=True),
    lambda p: p["candidates"][0].update(citation_validation="MISMATCH"),
    lambda p: p["review_only_candidates"][0].update(rejection_reason="PASS"),
])
def test_inconsistent_provenance_is_blocked(preview, change):
    change(preview)
    with pytest.raises(product().DraftExportError):
        product().build_reviewed_draft(preview, profile="FASHION", run_id=RUN_ID)


def test_reservation_is_unique_and_never_overwrites(preview, tmp_path, monkeypatch):
    module = product()
    with module.reserve_draft(tmp_path) as first:
        first.save(preview, profile="FASHION")
        saved = first.path.read_bytes()
        with pytest.raises(module.DraftExportError):
            first.save(preview, profile="FASHION")
        with module.reserve_draft(tmp_path) as second:
            assert first.run_id != second.run_id
            assert first.path != second.path
        from uuid import UUID

        monkeypatch.setattr(module, "uuid4", lambda: UUID(hex=first.run_id))
        with pytest.raises(module.DraftExportError):
            with module.reserve_draft(tmp_path):
                pytest.fail("existing file opened")
        assert first.path.read_bytes() == saved


def test_repository_and_missing_paths_are_blocked(tmp_path):
    module = product()
    root = Path(__file__).resolve().parents[3]
    nested_repo = tmp_path / "other-checkout"
    nested_repo.mkdir()
    (nested_repo / ".git").mkdir()
    for path in (root, root / "backend", tmp_path / "missing", nested_repo):
        with pytest.raises(module.DraftExportError):
            with module.reserve_draft(path):
                pytest.fail("invalid destination accepted")


def invoke_cli(endpoint, tmp_path, monkeypatch, *, path=None):
    from app.responses_web_search import d1_live_preview, demo_cli

    monkeypatch.setattr(d1_live_preview, "datetime", datetime)
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    output, error = Terminal(), Terminal()
    code = demo_cli.main(
        ["--profile", "FASHION", "--execute-live", "--draft-dir",
         str(tmp_path if path is None else path)],
        stdin=Terminal(PHRASE + "\n"), stdout=output, stderr=error,
        execution_at=INSTANT, http_transport=httpx2.MockTransport(endpoint.handle),
    )
    return code, output.getvalue(), error.getvalue()


def test_cli_saves_actual_mock_result_without_extra_request(
    endpoint, tmp_path, monkeypatch,
):
    endpoint.payload = payload_for("ready")
    code, stdout, _ = invoke_cli(endpoint, tmp_path, monkeypatch)
    assert code == 0
    assert len(endpoint.calls) == 1
    report = json.loads(stdout)
    saved = json.loads(Path(report["draft_file"]).read_text(encoding="utf-8"))
    assert saved["approved_record_count"] == 0
    assert saved["records"][0]["original_failure"] is None
    assert API_KEY not in json.dumps(saved)


def test_cli_invalid_destination_prevents_paid_request(endpoint, tmp_path, monkeypatch):
    code, _, error = invoke_cli(
        endpoint, tmp_path, monkeypatch, path=tmp_path / "missing",
    )
    assert code == 1
    assert endpoint.calls == []
    assert "DRAFT" in error


def test_cli_write_failure_never_reissues_search(endpoint, tmp_path, monkeypatch):
    endpoint.payload = payload_for("ready")

    def fail(*args, **kwargs):
        raise OSError("private filesystem error")

    monkeypatch.setattr(product().DraftFile, "save", fail)
    code, _, error = invoke_cli(endpoint, tmp_path, monkeypatch)
    assert code == 1
    assert len(endpoint.calls) == 1
    assert "DRAFT_WRITE_FAILED_NO_RETRY" in error
    assert "private filesystem error" not in error


@pytest.mark.parametrize("stdin", [
    Terminal("wrong\n"), Terminal(PHRASE + "\n", tty=False),
])
def test_export_option_keeps_approval_before_file_or_http(endpoint, tmp_path, stdin):
    from app.responses_web_search.demo_cli import main

    assert main(
        ["--profile", "GAME", "--execute-live", "--draft-dir", str(tmp_path)],
        stdin=stdin, stdout=Terminal(), stderr=Terminal(),
        execution_at=INSTANT, http_transport=httpx2.MockTransport(endpoint.handle),
    ) == 1
    assert endpoint.calls == []
    assert list(tmp_path.iterdir()) == []


def test_timeout_is_retained_without_invented_candidates(
    endpoint, tmp_path, monkeypatch,
):
    endpoint.transport_error = httpx2.ReadTimeout
    code, stdout, _ = invoke_cli(endpoint, tmp_path, monkeypatch)
    assert code == 1
    assert len(endpoint.calls) == 1
    report = json.loads(stdout)
    batch = json.loads(Path(report["draft_file"]).read_text(encoding="utf-8"))
    assert batch["records"] == []
    assert batch["search_runs"][0]["evidence"]["search_execution"] == "UNKNOWN"
