"""IGDB operational binding tests: no real secrets, network or MariaDB."""

import io
import json
import stat
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.igdb_adapter import (
    IGDB_ID,
    SCOPE,
    SOURCE_ID,
    VISITS_ID,
    IgdbBlocked,
)
from app.trend_collection.supply_adapter import ADAPTERS, SupplyBlocked
from scripts import run_auto_supply as supply


class CredentialStream(io.BytesIO):
    def fileno(self):
        return 99


def test_registry_entry_is_unbound_and_denies_unauthorized_io():
    entry = ADAPTERS[SOURCE_ID]
    assert entry.scope == SCOPE
    with pytest.raises(SupplyBlocked, match="IGDB_CREDENTIALS_UNAVAILABLE"):
        entry.collect_preview()
    with pytest.raises(SupplyBlocked, match="IGDB_CREDENTIALS_UNAVAILABLE"):
        entry.verify({}, datetime.now(timezone.utc))


def test_missing_igdb_credentials_fail_closed(monkeypatch):
    monkeypatch.setattr(
        supply, "_root_file", Mock(side_effect=FileNotFoundError),
    )
    with pytest.raises(SupplyBlocked, match="IGDB_CREDENTIALS_UNAVAILABLE"):
        supply._igdb_query("collect")


def test_godot_registry_path_does_not_load_igdb_credentials(monkeypatch):
    from app.trend_collection.godot_release_collector import REPO

    probe = Mock(side_effect=AssertionError("unexpected IGDB credentials"))
    monkeypatch.setattr(supply, "_igdb_query", probe)
    source = supply.ApprovedSource(REPO, supply.ADAPTERS[REPO].scope, "godot")
    assert supply._operational_adapter(source, "collect") is supply.ADAPTERS[REPO]
    assert supply._operational_adapter(source, "write") is supply.ADAPTERS[REPO]
    probe.assert_not_called()


def test_per_role_credential_files_are_separate_and_never_echoed(monkeypatch):
    reads = []
    credentials = {"client_id": "testclient", "client_secret": "test-secret"}

    def reader(path, *, secret=False):
        reads.append((path.name, secret))
        return CredentialStream(json.dumps(credentials).encode())

    monkeypatch.setattr(supply, "_root_file", reader)
    monkeypatch.setattr(
        supply.os, "fstat",
        lambda _: SimpleNamespace(st_gid=1000, st_mode=stat.S_IFREG | 0o640),
    )
    monkeypatch.setattr(supply.os, "getegid", lambda: 1000)
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(supply, "IgdbClient", factory)

    assert supply._igdb_query("collect") is client.query
    assert supply._igdb_query("write") is client.query
    assert reads == [
        ("igdb-collect-credentials.json", True),
        ("igdb-write-credentials.json", True),
    ]
    assert factory.call_count == 2
    factory.assert_any_call("testclient", "test-secret")
    with pytest.raises(SupplyBlocked, match="IGDB_EXECUTION_ROLE_INVALID"):
        supply._igdb_query("invalid")


@pytest.mark.parametrize("gid,mode", [
    (1001, 0o640), (1000, 0o600), (1000, 0o644), (1000, 0o660),
])
def test_igdb_credentials_require_exact_principal_group_and_mode(
    monkeypatch, gid, mode,
):
    monkeypatch.setattr(
        supply, "_root_file",
        lambda path, *, secret=False: CredentialStream(
            b'{"client_id":"fixture","client_secret":"fixture"}'
        ),
    )
    monkeypatch.setattr(
        supply.os, "fstat",
        lambda _: SimpleNamespace(st_gid=gid, st_mode=stat.S_IFREG | mode),
    )
    monkeypatch.setattr(supply.os, "getegid", lambda: 1000)
    client = Mock()
    monkeypatch.setattr(supply, "IgdbClient", client)
    with pytest.raises(SupplyBlocked, match="IGDB_CREDENTIAL_SCOPE_INVALID"):
        supply._igdb_query("collect")
    client.assert_not_called()


def test_igdb_requires_profile_source_scope():
    raw = {
        "enabled": True, "profile_id": supply.PROFILE,
        "policy_version": supply.VERSION,
        "sources": [{
            "source_id": SOURCE_ID, "scope": SCOPE,
            "rights": dict(supply.RIGHTS), "rights_ref": "igdb-rights-evidence",
        }],
        "environment": "local", "collector_uid": 101, "writer_uid": 102,
        "port": 3309, "database": "trend_leader",
        "current_user": "trend_auto_writer@host",
        "journal_id": "a" * 32, "journal_device": 1, "journal_inode": 2,
        "approved_at": "2026-11-20T00:00:00+00:00",
        "valid_until": "2026-12-20T00:00:00+00:00",
        "approved_by": "fixture", "g5_ref": "g5-evidence", "g6_ref": "g6-evidence",
    }
    now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    accepted = supply.parse_profile(raw, now)
    assert accepted.source(SOURCE_ID).scope == SCOPE
    wrong = {**raw, "sources": [{**raw["sources"][0], "scope": "OTHER"}]}
    with pytest.raises(SupplyBlocked, match="SOURCE_SCOPE_NOT_APPROVED"):
        supply.parse_profile(wrong, now)


def _fixture_query():
    calculated = int(
        (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    )
    calls = []

    def query(endpoint, body):
        calls.append(endpoint)
        if endpoint == "popularity_types":
            return [{
                "id": VISITS_ID, "name": "Visits",
                "external_popularity_source": {"id": IGDB_ID, "name": "IGDB"},
            }]
        if endpoint == "popularity_primitives":
            return [{
                "game_id": 1, "value": 0.01,
                "calculated_at": calculated, "popularity_type": VISITS_ID,
                "external_popularity_source": IGDB_ID,
            }]
        if endpoint == "games":
            return [{
                "id": 1, "name": "Fixture Game 1",
                "url": "https://www.igdb.com/games/fixture-1",
                "game_type": {"type": "Main Game"},
                "platforms": [{"id": 6, "name": "PC (Microsoft Windows)"}],
                "themes": [{"id": 1, "name": "Action"}],
                "age_ratings": [{
                    "organization": {"id": 5, "name": "GRAC"},
                    "rating_category": {"id": 24, "rating": "12+"},
                }],
            }]
        raise AssertionError("Unexpected endpoint")

    return query, calls


def test_igdb_collect_and_independent_writer_bind_verified_snapshot(monkeypatch):
    query, requests = _fixture_query()
    roles = []

    def credential_query(role):
        roles.append(role)
        return query

    monkeypatch.setattr(supply, "_igdb_query", credential_query)
    source = supply.ApprovedSource(SOURCE_ID, SCOPE, "igdb-rights-evidence")
    envelope = supply.collect_envelope(source)
    assert envelope["source_id"] == SOURCE_ID
    assert envelope["preview"]["candidate_identity"] == "igdb-game:1"
    assert envelope["preview"]["publication_status"] == "NOT_FOR_PUBLICATION"

    profile = Mock()
    profile.source.return_value = source
    profile.target = "local:127.0.0.1:3309/trend_leader/trend_auto_writer@host"
    writer = Mock(return_value="COMMITTED")
    monkeypatch.setattr(supply, "_write", writer)
    monkeypatch.setattr(supply, "OperationalJournal", Mock())

    result = supply.run_writer(profile, envelope)
    snapshot = writer.call_args.args[1]
    assert result == {"status": "COMMITTED", "candidate_identity": "igdb-game:1"}
    assert roles == ["collect", "write"]
    assert requests == [
        "popularity_types", "popularity_primitives", "games",
        "popularity_types", "popularity_primitives", "games",
    ]
    assert snapshot.candidate_identity == "igdb-game:1"
    assert snapshot.target == profile.target
    assert snapshot.platform == "ETC"
    assert snapshot.parent_code == "GAME"
    assert snapshot.source_url == "https://www.igdb.com/games/fixture-1"
    profile.source.assert_called_once_with(SOURCE_ID)
    writer.assert_called_once()



def test_independent_igdb_verification_rejects_tampered_preview(monkeypatch):
    query, _ = _fixture_query()
    monkeypatch.setattr(supply, "_igdb_query", lambda role: query)
    source = supply.ApprovedSource(SOURCE_ID, SCOPE, "igdb-rights-evidence")
    envelope = supply.collect_envelope(source)
    envelope["preview"] = {**envelope["preview"], "rank": 99}

    profile = Mock()
    profile.source.return_value = source
    writer = Mock()
    monkeypatch.setattr(supply, "_write", writer)
    with pytest.raises(IgdbBlocked, match="PREVIEW_MISMATCH"):
        supply.run_writer(profile, envelope)
    writer.assert_not_called()


def test_igdb_without_eligible_games_skips_before_writer(monkeypatch):
    query, calls = _fixture_query()

    def no_candidates(endpoint, body):
        if endpoint == "popularity_primitives":
            calls.append(endpoint)
            return []
        return query(endpoint, body)

    monkeypatch.setattr(supply, "_igdb_query", lambda role: no_candidates)
    source = supply.ApprovedSource(SOURCE_ID, SCOPE, "igdb-rights-evidence")
    assert supply.collect_envelope(source) == {
        "source_id": SOURCE_ID, "status": "NO_ELIGIBLE_CANDIDATE",
    }
    assert calls == ["popularity_types", "popularity_primitives"]
