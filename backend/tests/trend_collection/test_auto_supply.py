"""Operational connection tests; no live HTTP or MariaDB credentials."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock

import pytest

from app.trend_collection.godot_release_collector import RELEASES, REPO, _parse
from app.trend_collection.rule_first_preview import build_rule_first_preview
from app.trend_collection.supply_adapter import (
    GodotAdapter,
    SupplyBlocked,
    bind_snapshot,
)
from scripts import run_auto_supply as supply
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal

NOW = datetime(2026, 11, 19, 7, tzinfo=timezone.utc)
RAW = {"id": 42, "tag_name": "4.8-beta4", "draft": False, "prerelease": True,
       "html_url": f"https://github.com/{REPO}/releases/tag/4.8-beta4",
       "published_at": "2026-11-18T22:01:47Z"}


def profile_data():
    return {
        "enabled": True, "profile_id": supply.PROFILE, "policy_version": supply.VERSION,
        "sources": [{"source_id": REPO, "scope": "GODOT_FACTS_LINK_V1",
                     "rights": dict(supply.RIGHTS), "rights_ref": "test-rights-ref"}],
        "environment": "local", "collector_uid": 101, "writer_uid": 102,
        "port": 3309, "database": "trend_leader",
        "current_user": "trend_auto_writer@host",
        "journal_id": "a" * 32, "journal_device": 1, "journal_inode": 2,
        "approved_at": (NOW - timedelta(days=1)).isoformat(),
        "valid_until": (NOW + timedelta(days=1)).isoformat(),
        "approved_by": "fixture_operator",
        "g5_ref": "test-g5-reference", "g6_ref": "test-g6-reference",
    }


def profile():
    return supply.parse_profile(profile_data(), NOW)


def candidate():
    return build_rule_first_preview(_parse(RAW), NOW)


def snapshot():
    verified = GodotAdapter(lambda _: RAW).verify(candidate(), NOW)
    return bind_snapshot(verified, policy=supply.VERSION, target=profile().target)


@pytest.mark.parametrize("changes", [
    {"enabled": False}, {"sources": []}, {"policy_version": "old"},
    {"sources": [{"source_id": REPO, "rights": {"access": "ALLOWED"}}]},
    {"sources": [{**profile_data()["sources"][0], "scope": "all-content"}]},
    {"collector_uid": 102}, {"writer_uid": 0}, {"port": 3307},
    {"database": "trend_leader_writer_test"}, {"current_user": "root@host"},
    {"valid_until": NOW.isoformat()}, {"g6_ref": "PASS"}, {"extra": True},
])
def test_invalid_profile_rejected(changes):
    with pytest.raises(SupplyBlocked):
        supply.parse_profile({**profile_data(), **changes}, NOW)


def test_adapter_rechecks_fixed_detail_and_keeps_generic_fields():
    request = Mock(return_value=RAW)
    item = GodotAdapter(request).verify(candidate(), NOW)
    request.assert_called_once_with(f"{RELEASES}/42")
    assert item.parent_code == "IT_DIGITAL" and item.is_primary is True
    assert item.source_url == RAW["html_url"]
    assert item.target == "UNBOUND_OPERATIONAL"


@pytest.mark.parametrize("changes", [
    {"summary": "not verified"}, {"publish_authorization": "PASS"},
    {"proposed_source": {"source_url": "https://example.invalid"}},
    {"observed_at_utc": (NOW - timedelta(minutes=11)).isoformat()},
    {"candidate_identity": "arbitrary:1"},
])
def test_adapter_rejects_tampering(changes):
    with pytest.raises(SupplyBlocked):
        GodotAdapter(lambda _: RAW).verify({**candidate(), **changes}, NOW)


def test_independent_detail_change_is_rejected():
    with pytest.raises(SupplyBlocked):
        GodotAdapter(lambda _: {**RAW, "id": 43}).verify(candidate(), NOW)


def test_unapproved_runtime_cannot_connect(monkeypatch, capsys):
    connector = Mock()
    monkeypatch.setattr(supply, "_make_engine", connector)
    monkeypatch.setattr(supply.sys, "argv", ["run_auto_supply", "collect"])
    monkeypatch.setattr(supply.sys, "platform", "win32")
    assert supply.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "HOLD"
    connector.assert_not_called()


def test_source_mismatch_does_not_connect(monkeypatch):
    connector = Mock()
    monkeypatch.setattr(supply, "_make_engine", connector)
    with pytest.raises(SupplyBlocked):
        supply.run_writer(profile(), {"source_id": "unapproved",
                                      "preview": candidate()})
    connector.assert_not_called()


def test_journal_unresolved_blocks_before_connector(monkeypatch):
    monkeypatch.setattr(supply, "_assert_current", Mock())
    connector = Mock()
    monkeypatch.setattr(supply, "_make_engine", connector)
    journal = Mock()
    journal.check_ready.side_effect = JournalBlocked("JOURNAL_UNRESOLVED_ATTEMPT")
    with pytest.raises(JournalBlocked):
        supply._write(profile(), snapshot(), journal)
    connector.assert_not_called()


def _mock_writer(monkeypatch, *, duplicate="NEW", failure=None, expire=False):
    engine, journal = MagicMock(), Mock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.exec_driver_sql.return_value.scalar_one.return_value = 1
    check = Mock(side_effect=[None, None, SupplyBlocked("REVOKED")] if expire else None)
    monkeypatch.setattr(supply, "_assert_current", check)
    monkeypatch.setattr(supply, "_make_engine", Mock(return_value=engine))
    monkeypatch.setattr(supply, "_verify_session", Mock())
    monkeypatch.setattr(supply, "_category_id", Mock(return_value=2))
    monkeypatch.setattr(supply, "inspect_snapshot", Mock(return_value=duplicate))
    insert = Mock(side_effect=failure)
    monkeypatch.setattr(supply, "insert_trend_item", insert)
    return conn, journal, insert


def test_write_claims_before_dml_and_commits(monkeypatch):
    conn, journal, insert = _mock_writer(monkeypatch)
    event_log = []
    journal.claim.side_effect = lambda *_: event_log.append("STARTED")
    insert.side_effect = lambda *_a, **_k: event_log.append("INSERT")
    conn.commit.side_effect = lambda: event_log.append("COMMIT")
    journal.finish.side_effect = lambda *a: event_log.append(a[-1])
    assert supply._write(profile(), snapshot(), journal) == "COMMITTED"
    assert event_log == ["STARTED", "INSERT", "COMMIT", "COMMITTED"]
    assert insert.call_args.kwargs["status"] == "ACTIVE"
    assert insert.call_args.kwargs["is_primary"] is True


def test_duplicate_skips_no_journal_claim_or_insert(monkeypatch):
    conn, journal, insert = _mock_writer(monkeypatch, duplicate="SKIP_EXISTING_RELEASE")
    assert supply._write(profile(), snapshot(), journal) == "SKIP_EXISTING_RELEASE"
    journal.claim.assert_not_called()
    insert.assert_not_called()
    conn.commit.assert_not_called()


@pytest.mark.parametrize("failure,expire", [(RuntimeError(), False), (None, True)])
def test_failure_and_precommit_revocation_roll_back(monkeypatch, failure, expire):
    conn, journal, _ = _mock_writer(monkeypatch, failure=failure, expire=expire)
    assert supply._write(profile(), snapshot(), journal) == "HOLD"
    conn.commit.assert_not_called()
    assert journal.finish.call_args.args[-1] == "ROLLED_BACK"


def test_unknown_commit_never_reported_as_success(monkeypatch):
    conn, journal, _ = _mock_writer(monkeypatch)
    conn.commit.side_effect = RuntimeError("lost response")
    assert supply._write(profile(), snapshot(), journal) == "HOLD"
    assert journal.finish.call_args.args[-1] == "COMMIT_UNKNOWN"


def test_operational_journal_reuse_is_separate_from_synthetic(tmp_path):
    path = tmp_path / "ops.sqlite3"
    journal = SyntheticJournal(path, "a" * 32)
    journal.initialize_for_synthetic_test()
    journal.profile_id = supply.PROFILE
    journal.policy_version = supply.VERSION
    journal.mode = "AUTHORIZED_OPERATIONAL"
    journal.target = profile().target
    journal.check_ready()
    journal.claim("auto-fixture", "b" * 64, "c" * 32)
    with pytest.raises(JournalBlocked):
        journal.check_ready()
    journal.finish("auto-fixture", "b" * 64, "c" * 32, "COMMITTED")
    journal.check_ready()
    with pytest.raises(JournalBlocked):
        journal.claim("auto-fixture", "b" * 64, "d" * 32)
    with pytest.raises(JournalBlocked):
        SyntheticJournal(path, "a" * 32).check_ready()


def test_new_adapter_does_not_change_writer(monkeypatch):
    adapter = Mock(scope="OTHER_FACTS_V1")
    adapter.verify.return_value = snapshot()
    monkeypatch.setitem(supply.ADAPTERS, "other-source", adapter)
    raw = profile_data()
    raw["sources"].append({"source_id": "other-source", "scope": "OTHER_FACTS_V1",
                           "rights": dict(supply.RIGHTS), "rights_ref": "other-ref"})
    approved = supply.parse_profile(raw, NOW)
    writer = Mock(return_value="COMMITTED")
    monkeypatch.setattr(supply, "_write", writer)
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    assert supply.run_writer(approved, {"source_id": "other-source", "preview": {}})[
        "status"] == "COMMITTED"
    adapter.verify.assert_called_once_with({}, NOW)
    assert writer.call_args.args[1].target == approved.target
    with pytest.raises(SupplyBlocked):
        approved.source(None)
