"""Protected role binding and no-candidate contracts, without live I/O."""

import io
import stat
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.searchapi_supply_snapshot import (
    SCOPE,
    SOURCE_ID,
    AutomaticSearchApiAdapter,
)
from app.trend_collection.supply_adapter import ADAPTERS, SupplyBlocked
from scripts import run_auto_supply as supply

NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)


class CredentialStream(io.BytesIO):
    def fileno(self):
        return 99


def source():
    return supply.ApprovedSource(SOURCE_ID, SCOPE, "fixture-evidence")


def test_registry_descriptor_is_inert():
    adapter = ADAPTERS[SOURCE_ID]
    assert adapter.scope == SCOPE
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_ROLE_NOT_BOUND"):
        adapter.collect_preview()
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_ROLE_NOT_BOUND"):
        adapter.verify({}, NOW)


def test_collector_reads_only_its_key_writer_never_reads_key(monkeypatch):
    reader = Mock(return_value=CredentialStream(b'{"api_key":"fixture-key"}'))
    monkeypatch.setattr(supply, "_root_file", reader)
    monkeypatch.setattr(supply, "os", SimpleNamespace(
        fstat=lambda _: SimpleNamespace(st_gid=1000, st_mode=stat.S_IFREG | 0o640),
        getegid=lambda: 1000,
    ))
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(supply, "SearchApiClient", factory)
    collector = supply._operational_adapter(source(), "collect")
    writer = supply._operational_adapter(source(), "write")
    assert type(collector) is AutomaticSearchApiAdapter
    assert type(writer) is AutomaticSearchApiAdapter
    reader.assert_called_once_with(
        supply.CONTROL / "searchapi-collect-credentials.json", secret=True,
    )
    factory.assert_called_once_with("fixture-key")
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_COLLECTOR_REQUIRED"):
        writer.collect_preview()
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_EXECUTION_ROLE_INVALID"):
        supply._operational_adapter(source(), "invalid")


@pytest.mark.parametrize("gid,mode", [(1001, 0o640), (1000, 0o644), (1000, 0o660)])
def test_key_file_requires_role_group_and_exact_mode(monkeypatch, gid, mode):
    monkeypatch.setattr(
        supply, "_root_file",
        Mock(return_value=CredentialStream(b'{"api_key":"fixture-key"}')),
    )
    monkeypatch.setattr(supply, "os", SimpleNamespace(
        fstat=lambda _: SimpleNamespace(st_gid=gid, st_mode=stat.S_IFREG | mode),
        getegid=lambda: 1000,
    ))
    factory = Mock()
    monkeypatch.setattr(supply, "SearchApiClient", factory)
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_CREDENTIAL_SCOPE_INVALID"):
        supply._operational_adapter(source(), "collect")
    factory.assert_not_called()


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(supply, "_root_file", Mock(side_effect=FileNotFoundError))
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_CREDENTIALS_UNAVAILABLE"):
        supply._operational_adapter(source(), "collect")


def test_empty_collector_does_not_become_writer_envelope(monkeypatch):
    adapter = Mock()
    adapter.collect_preview.return_value = None
    bind = Mock(return_value=adapter)
    monkeypatch.setattr(supply, "_operational_adapter", bind)
    assert supply.collect_envelope(source()) == {
        "source_id": SOURCE_ID, "status": "NO_ELIGIBLE_CANDIDATE",
    }
    bind.assert_called_once_with(source(), "collect")
    adapter.collect_preview.assert_called_once_with()
    with pytest.raises(SupplyBlocked, match="GAME_CURSOR_INVALID"):
        supply.collect_envelope(source(), after_game_id=87622)
    with pytest.raises(SupplyBlocked, match="SOURCE_ENVELOPE_MISMATCH"):
        supply.run_writer(Mock(), {
            "source_id": SOURCE_ID, "status": "NO_ELIGIBLE_CANDIDATE",
        })


def test_writer_uses_approved_role_and_never_loads_collector_key(monkeypatch):
    profile = Mock()
    profile.source.return_value = source()
    adapter = Mock()
    bind = Mock(return_value=adapter)
    secret = Mock(side_effect=AssertionError("writer must not access key"))
    snapshot = Mock(candidate_identity="searchapi-event:" + "a" * 64)
    adapter.verify.return_value = snapshot
    monkeypatch.setattr(supply, "_operational_adapter", bind)
    monkeypatch.setattr(supply, "_searchapi_client", secret)
    monkeypatch.setattr(supply, "bind_snapshot", Mock(return_value=snapshot))
    monkeypatch.setattr(supply, "OperationalJournal", Mock())
    write = Mock(return_value="COMMITTED")
    monkeypatch.setattr(supply, "_write", write)
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    preview = {"case_key": "a" * 64}
    assert supply.run_writer(profile, {"source_id": SOURCE_ID, "preview": preview}) == {
        "status": "COMMITTED", "candidate_identity": snapshot.candidate_identity,
    }
    profile.source.assert_called_once_with(SOURCE_ID)
    bind.assert_called_once_with(source(), "write")
    adapter.verify.assert_called_once_with(preview, NOW)
    secret.assert_not_called()
    write.assert_called_once()
