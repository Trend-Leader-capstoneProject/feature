"""E1 AL-02 negative tests. Test only: no database or service connection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.b_lite_e1_hold_boundary import (
    MAX_APPROVAL_BYTES,
    inspect_manual_approval,
    main,
    test_only_writer_entry_probe as probe_writer_entry,
)


def comparison_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def assert_denied(result: dict[str, object], reason: str) -> None:
    assert result == {
        "status": "BLOCKED",
        "reason": reason,
        "authorized_to_publish": False,
        "g6_approval": "HOLD",
        "database_connections": 0,
        "database_writes": 0,
    }


def test_missing_approval_document_never_calls_connector(tmp_path: Path) -> None:
    calls: list[str] = []

    def connector() -> object:
        calls.append("CONNECTED")
        raise AssertionError("Connector must not be invoked")

    result = probe_writer_entry(
        tmp_path / "not-found.md", "a" * 64, connector=connector
    )
    assert_denied(result, "APPROVAL_DOCUMENT_MISSING")
    assert calls == []


@pytest.mark.parametrize(
    "document",
    [b"g6_status: HOLD\n", b"g6_status: PASS\n", b"approved: true\n"],
)
def test_document_claims_cannot_authorize_even_with_matching_hash(
    tmp_path: Path, document: bytes
) -> None:
    file = tmp_path / "approval.md"
    file.write_bytes(document)
    calls: list[str] = []

    def connector() -> object:
        calls.append("CONNECTED")
        raise AssertionError("Connector must not be invoked")

    result = probe_writer_entry(file, comparison_hash(document), connector=connector)
    assert_denied(result, "G6_INDEPENDENT_AUTH_NOT_VERIFIED")
    assert calls == []


def test_changed_document_blocks_before_connector(tmp_path: Path) -> None:
    file = tmp_path / "approval.md"
    original = b"g6_status: HOLD\n"
    file.write_bytes(original)
    known_hash = comparison_hash(original)
    file.write_bytes(b"g6_status: PASS\n")
    calls = 0

    def connector() -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("Connector must not be invoked")

    result = probe_writer_entry(file, known_hash, connector=connector)
    assert_denied(result, "APPROVAL_DOCUMENT_HASH_MISMATCH")
    assert calls == 0


def test_missing_approval_file_argument_blocks() -> None:
    assert_denied(
        inspect_manual_approval(None, "a" * 64), "APPROVAL_DOCUMENT_MISSING"
    )


def test_missing_comparison_value_blocks(tmp_path: Path) -> None:
    file = tmp_path / "approval.md"
    file.write_text("G6=HOLD", encoding="utf-8")
    assert_denied(inspect_manual_approval(file, None), "COMPARISON_HASH_MISSING")


def test_malformed_comparison_value_blocks(tmp_path: Path) -> None:
    file = tmp_path / "approval.md"
    file.write_text("G6=HOLD", encoding="utf-8")
    assert_denied(inspect_manual_approval(file, "PASS"), "INVALID_COMPARISON_HASH")


def test_directory_cannot_be_approval_file(tmp_path: Path) -> None:
    assert_denied(
        inspect_manual_approval(tmp_path, "a" * 64), "APPROVAL_DOCUMENT_MISSING"
    )


def test_oversized_document_blocks(tmp_path: Path) -> None:
    file = tmp_path / "approval.md"
    file.write_bytes(b"x" * (MAX_APPROVAL_BYTES + 1))
    assert_denied(
        inspect_manual_approval(file, "a" * 64), "APPROVAL_DOCUMENT_TOO_LARGE"
    )


def test_cli_reports_block_only_no_publish_option(tmp_path: Path, capsys) -> None:
    contents = b"g6_status: PASS\n"
    file = tmp_path / "approval.md"
    file.write_bytes(contents)
    rc = main(
        ["--approval-file", str(file), "--comparison-sha256", comparison_hash(contents)]
    )
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert_denied(data, "G6_INDEPENDENT_AUTH_NOT_VERIFIED")


def test_cli_rejects_apply_flag() -> None:
    with pytest.raises(SystemExit) as error:
        main(["--apply"])
    assert error.value.code == 2
