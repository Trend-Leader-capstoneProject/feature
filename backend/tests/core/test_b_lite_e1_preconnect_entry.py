"""Minimal E1-W0 integration: E0 input plus AL-02 deny, no DB connection."""

from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path

import pytest

from scripts import b_lite_e1_preconnect_entry as entry


def make_manifest(tmp_path: Path) -> Path:
    file = tmp_path / "manifest.json"
    file.write_text(
        json.dumps(
            {
                "schema": "B_LITE_EXHIBITION_REVIEW_V1",
                "profile_id": "MVP_A_EXHIBITION_20261118_19",
                "approval_scope": "REVIEW_ONLY",
                "g6_status": "HOLD",
                "batch_id": "E1-W0-SYNTHETIC",
                "records": [
                    {
                        "kind": "SYNTHETIC_DEMO",
                        "title": "【DEMO】 가상 시연 주제",
                        "summary": (
                            "가상의 시연 데이터입니다. "
                            "실제 검색·수집 결과가 아닙니다."
                        ),
                        "thumbnail_url": None,
                        "google_rss_derived": False,
                        "parent_code": "GAME",
                        "child_name": "기타",
                        "source_url": None,
                        "source_title": None,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return file


def assert_denied(result: dict[str, object], reason: str) -> None:
    assert result["status"] == "BLOCKED"
    assert result["reason"] == reason
    assert result["authorized_to_publish"] is False
    assert result["g6_approval"] == "HOLD"
    assert result["database_connections"] == 0
    assert result["database_writes"] == 0


def test_missing_approval_blocks(tmp_path: Path) -> None:
    result = entry.inspect_preconnect(make_manifest(tmp_path), None, None)
    assert_denied(result, "APPROVAL_DOCUMENT_MISSING")


@pytest.mark.parametrize("text", ["G6: HOLD", "G6: PASS", "approved: true"])
def test_matching_hash_never_authorizes(tmp_path: Path, text: str) -> None:
    approval = tmp_path / "approval.md"
    approval.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(approval.read_bytes()).hexdigest()
    result = entry.inspect_preconnect(make_manifest(tmp_path), approval, digest)
    assert_denied(result, "G6_INDEPENDENT_AUTH_NOT_VERIFIED")


def test_hash_mismatch_blocks(tmp_path: Path) -> None:
    approval = tmp_path / "approval.md"
    approval.write_text("G6: HOLD", encoding="utf-8")
    result = entry.inspect_preconnect(make_manifest(tmp_path), approval, "a" * 64)
    assert_denied(result, "APPROVAL_DOCUMENT_HASH_MISMATCH")


def test_invalid_e0_manifest_blocks_first(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["g6_status"] = "PASS"
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result = entry.inspect_preconnect(manifest, None, None)
    assert_denied(result, "G6_NOT_VERIFIABLE")


def test_unexpected_e1_allow_fails_closed(tmp_path: Path, monkeypatch) -> None:
    def forged_approval(*_args) -> dict[str, object]:
        return {"status": "PASS", "authorized_to_publish": True}

    monkeypatch.setattr(entry, "inspect_manual_approval", forged_approval)
    result = entry.inspect_preconnect(make_manifest(tmp_path), None, None)
    assert_denied(result, "E1_UNEXPECTED_AUTHORIZATION")


def test_unexpected_e0_allow_fails_closed(tmp_path: Path, monkeypatch) -> None:
    def forged_e0(_file: Path) -> dict[str, object]:
        return {"status": "REVIEW_ONLY", "authorized_to_publish": True}

    monkeypatch.setattr(entry, "check_file", forged_e0)
    result = entry.inspect_preconnect(make_manifest(tmp_path), None, None)
    assert_denied(result, "E0_UNEXPECTED_AUTHORIZATION")


def test_unexpected_e1_db_claim_fails_closed(tmp_path: Path, monkeypatch) -> None:
    def forged_e1(*_args) -> dict[str, object]:
        return {
            "status": "BLOCKED",
            "authorized_to_publish": False,
            "g6_approval": "HOLD",
            "database_connections": 1,
            "database_writes": 0,
        }

    monkeypatch.setattr(entry, "inspect_manual_approval", forged_e1)
    result = entry.inspect_preconnect(make_manifest(tmp_path), None, None)
    assert_denied(result, "E1_UNEXPECTED_AUTHORIZATION")


def test_never_imports_actual_backend_db(tmp_path: Path, monkeypatch) -> None:
    actual_import = builtins.__import__
    requested = []

    def trap_import(name, *args, **kwargs):
        if name.startswith("app.db"):
            requested.append(name)
            raise AssertionError("DB module must never be imported")
        return actual_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", trap_import)
    result = entry.inspect_preconnect(make_manifest(tmp_path), None, None)
    assert_denied(result, "APPROVAL_DOCUMENT_MISSING")
    assert requested == []


def test_cli_never_supports_apply(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        entry.main(["--input", str(make_manifest(tmp_path)), "--apply"])
    assert error.value.code == 2
