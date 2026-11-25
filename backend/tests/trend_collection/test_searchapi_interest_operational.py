"""Interest operational role binding; protected files mocked, no real I/O."""

import io
import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.searchapi_interest import (
    SCOPE,
    SOURCE_ID,
    SearchInterestAdapter,
)
from app.trend_collection.supply_adapter import SupplyBlocked
from scripts import run_auto_supply as supply


class CredentialStream(io.BytesIO):
    def fileno(self):
        return 99


def _source():
    return supply.ApprovedSource(SOURCE_ID, SCOPE, "fixture-evidence")


@pytest.mark.parametrize("role", ["collect", "write"])
def test_role_binding_reads_only_its_key_and_common_catalog(monkeypatch, role):
    def root_file(path, *, secret=False):
        if secret:
            return CredentialStream(b'{"api_key":"fixture-key"}')
        return io.BytesIO(
            '{"작품2":["ENTERTAINMENT","드라마"]}'.encode(),
        )

    reader = Mock(side_effect=root_file)
    monkeypatch.setattr(supply, "_root_file", reader)
    monkeypatch.setattr(supply, "os", SimpleNamespace(
        fstat=lambda _: SimpleNamespace(st_gid=1000, st_mode=stat.S_IFREG | 0o640),
        getegid=lambda: 1000,
    ))
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(supply, "SearchApiClient", factory)
    adapter = supply._operational_adapter(_source(), role)
    assert type(adapter) is SearchInterestAdapter
    assert reader.call_args_list[0].args == (
        supply.CONTROL / f"searchapi-{role}-credentials.json",
    )
    assert reader.call_args_list[0].kwargs == {"secret": True}
    assert reader.call_args_list[1].args == (
        supply.CONTROL / "searchapi-interest-topics.json",
    )
    assert reader.call_count == 2
    factory.assert_called_once_with("fixture-key")


def test_invalid_catalog_rejected_without_query(monkeypatch):
    monkeypatch.setattr(
        supply, "_root_file", Mock(return_value=io.BytesIO(b'{"topic":"GAME"}')),
    )
    with pytest.raises(SupplyBlocked, match="INTEREST_CATALOG_INVALID"):
        supply._interest_topics()


def test_no_candidate_uses_existing_controller_contract(monkeypatch):
    adapter = Mock()
    adapter.collect_preview.return_value = None
    monkeypatch.setattr(supply, "_operational_adapter", Mock(return_value=adapter))
    assert supply.collect_envelope(_source()) == {
        "source_id": SOURCE_ID, "status": "NO_ELIGIBLE_CANDIDATE",
    }
