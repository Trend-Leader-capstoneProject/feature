"""No database, network, credential, or approval fixtures are used here."""

import json
from pathlib import Path

import pytest

from scripts.b_lite_exhibition_once import (
    DEMO_NOTICE,
    PROFILE,
    SCHEMA,
    PreflightBlocked,
    check_file,
    inspect_manifest,
    main,
)


def real_record():
    return {
        "kind": "REVIEWED_REAL",
        "title": "검토 대상 자체 작성 주제",
        "summary": None,
        "thumbnail_url": None,
        "google_rss_derived": False,
        "parent_code": "IT_DIGITAL",
        "child_name": "소프트웨어",
        "source_url": "https://www.python.org/downloads/",
        "source_title_origin": "NONE",
        "source_title": None,
        "source_label_evidence_id": None,
        "source_review": "URL_TITLE_KEY_CLAIMS_VERIFIED",
        "review_evidence_id": "SAMPLE-ONLY-NOT-REAL-EVIDENCE",
        "content_ref": "sha256:" + "a" * 64,
    }


def demo_record():
    return {
        "kind": "SYNTHETIC_DEMO",
        "title": "【DEMO】 가상 시연 주제",
        "summary": DEMO_NOTICE,
        "thumbnail_url": None,
        "google_rss_derived": False,
        "parent_code": "GAME",
        "child_name": "기타",
        "source_url": None,
        "source_title": None,
    }


def manifest(*records):
    return {
        "schema": SCHEMA,
        "profile_id": PROFILE,
        "approval_scope": "REVIEW_ONLY",
        "g6_status": "HOLD",
        "batch_id": "SAMPLE-BATCH-001",
        "records": list(records),
    }


def assert_blocked(data, reason):
    with pytest.raises(PreflightBlocked, match=reason):
        inspect_manifest(data)


def test_valid_candidates_are_never_publishing_authorization():
    result = inspect_manifest(manifest(real_record(), demo_record()))
    assert result["status"] == "REVIEW_ONLY"
    assert result["real_candidates"] == 1
    assert result["demo_candidates"] == 1
    assert result["authorized_to_publish"] is False
    assert result["database_connections"] == result["database_writes"] == 0
    assert result["g4_evidence_authenticity"] == "NOT_VERIFIED"


@pytest.mark.parametrize("bad_status", ["PASS", "APPROVED", None, True])
def test_fake_or_missing_g6_status_blocked(bad_status):
    data = manifest(real_record())
    data["g6_status"] = bad_status
    assert_blocked(data, "G6_NOT_VERIFIABLE")


def test_missing_g4_evidence_blocked():
    data = manifest(real_record())
    del data["records"][0]["review_evidence_id"]
    assert_blocked(data, "G4_EVIDENCE_MISSING")


def test_missing_content_reference_blocked():
    data = manifest(real_record())
    data["records"][0]["content_ref"] = "NOT_VERIFIED"
    assert_blocked(data, "CONTENT_REF_MISSING")


def test_google_rss_declaration_blocked():
    data = manifest(real_record())
    data["records"][0]["google_rss_derived"] = True
    assert_blocked(data, "GOOGLE_RSS_NOT_EXCLUDED")


def test_unlabeled_synthetic_blocked():
    data = manifest(demo_record())
    data["records"][0]["title"] = "가상 시연 주제"
    assert_blocked(data, "DEMO_LABEL_MISSING")


def test_fake_synthetic_source_blocked():
    data = manifest(demo_record())
    data["records"][0]["source_url"] = "https://www.python.org/"
    assert_blocked(data, "DEMO_FAKE_SOURCE")


def test_non_https_external_source_blocked():
    data = manifest(real_record())
    data["records"][0]["source_url"] = "http://www.python.org/downloads/"
    assert_blocked(data, "INVALID_SOURCE_URL")


def test_editorial_source_requires_evidence():
    data = manifest(real_record())
    record = data["records"][0]
    record["source_title_origin"] = "EDITORIAL_LABEL"
    record["source_title"] = "팀 작성 출처 안내"
    assert_blocked(data, "INVALID_SOURCE_LABEL")
    record["source_label_evidence_id"] = "SAMPLE-LABEL-EVIDENCE"
    assert inspect_manifest(data)["status"] == "REVIEW_ONLY"


def test_duplicate_title_blocked():
    assert_blocked(manifest(real_record(), real_record()), "DUPLICATE_TITLE")


def test_invalid_db_target_binding_blocked():
    data = manifest(real_record())
    data["approval_scope"] = "PRODUCTION"
    assert_blocked(data, "SCOPE_NOT_REVIEW_ONLY")


def test_duplicate_json_key_blocked(tmp_path: Path):
    path = tmp_path / "dup.json"
    path.write_text('{"schema":"X","schema":"Y"}', encoding="utf-8")
    with pytest.raises(PreflightBlocked, match="DUPLICATE_JSON_KEY"):
        check_file(path)


def test_cli_no_execute_option(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--input", "anything.json", "--execute"])
    assert exc.value.code == 2


def test_cli_read_only_result(tmp_path: Path, capsys):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(manifest(demo_record()), ensure_ascii=False), encoding="utf-8")
    assert main(["--input", str(path)]) == 0
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["status"] == "REVIEW_ONLY"
    assert outcome["authorized_to_publish"] is False
    assert outcome["database_writes"] == 0


def test_unrecognized_publish_flag_blocked():
    data = manifest(real_record())
    data["execute"] = True
    assert_blocked(data, "UNRECOGNIZED_MANIFEST_FIELD")


def test_unhashable_category_is_blocked_not_crash():
    data = manifest(demo_record())
    data["records"][0]["parent_code"] = []
    assert_blocked(data, "INVALID_ROOT_CATEGORY")
