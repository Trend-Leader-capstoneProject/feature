"""Operational connection tests; no live HTTP or MariaDB credentials."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.godot_release_collector import (
    RELEASES,
    REPO,
    RateLimited,
    _parse,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview
from app.trend_collection.supply_adapter import (
    GODOT_ICON_URL,
    GODOT_IMAGE_SCOPE,
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


def test_one_g6_approval_covers_scheduled_cycles_until_expiry():
    """Approval is time-scoped, not a manual authorization per 6h cycle."""
    raw = profile_data()
    raw["approved_at"] = NOW.isoformat()
    raw["valid_until"] = (NOW + timedelta(days=30)).isoformat()
    reference = raw["g6_ref"]

    for offset in (timedelta(0), timedelta(hours=6),
                   timedelta(days=15), timedelta(days=29, hours=18)):
        accepted = supply.parse_profile(raw, NOW + offset)
        assert accepted.g6_ref == reference
        assert accepted.valid_until == raw["valid_until"]

    with pytest.raises(SupplyBlocked, match="APPROVAL_OUTSIDE_VALIDITY"):
        supply.parse_profile(raw, NOW + timedelta(days=30))


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


def test_independent_detail_preserves_rate_limit():
    request = Mock(side_effect=RateLimited(123456))
    with pytest.raises(RateLimited) as error:
        GodotAdapter(request).verify(candidate(), NOW)
    assert error.value.retry_not_before == 123456
    request.assert_called_once_with(f"{RELEASES}/42")


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


@pytest.mark.parametrize(("method", "stage"), [
    ("_verify_session", "SESSION"),
    ("_category_id", "CATEGORY_LOCK"),
    ("inspect_snapshot", "DUPLICATE_CHECK"),
])
def test_preclaim_hold_diagnostic_is_bounded(monkeypatch, method, stage):
    conn, journal, insert = _mock_writer(monkeypatch)
    error = OperationalError(
        "sensitive SQL", {"password": "secret"}, Exception(1205, "secret text"),
    )
    getattr(supply, method).side_effect = error
    diagnostic = {}
    assert supply._write(
        profile(), snapshot(), journal, diagnostic=diagnostic,
    ) == "HOLD"
    assert diagnostic == {
        "reason": f"WRITER_{stage}_FAILED", "db_error_code": 1205,
    }
    journal.claim.assert_not_called()
    journal.finish.assert_not_called()
    conn.commit.assert_not_called()
    insert.assert_not_called()


@pytest.mark.parametrize(("failure", "stage", "journal_state"), [
    ("insert", "PARENT_INSERT", "ROLLED_BACK"),
    ("commit", "COMMIT", "COMMIT_UNKNOWN"),
])
def test_postclaim_diagnostic_preserves_journal_state(
    monkeypatch, failure, stage, journal_state,
):
    conn, journal, insert = _mock_writer(monkeypatch)
    operation = insert if failure == "insert" else conn.commit
    operation.side_effect = RuntimeError("private upstream content")
    diagnostic = {}
    assert supply._write(
        profile(), snapshot(), journal, diagnostic=diagnostic,
    ) == "HOLD"
    assert diagnostic == {"reason": f"WRITER_{stage}_FAILED"}
    assert journal.finish.call_args.args[-1] == journal_state


def test_run_writer_propagates_safe_hold_diagnostic(monkeypatch):
    adapter = Mock()
    adapter.verify.return_value = snapshot()
    monkeypatch.setattr(supply, "_operational_adapter", Mock(return_value=adapter))
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    monkeypatch.setattr(supply, "OperationalJournal", Mock())

    def hold(*args, diagnostic):
        diagnostic.update(reason="WRITER_CATEGORY_LOCK_FAILED", db_error_code=1205)
        return "HOLD"

    monkeypatch.setattr(supply, "_write", hold)
    result = supply.run_writer(profile(), {"source_id": REPO, "preview": {}})
    assert result == {
        "status": "HOLD", "candidate_identity": snapshot().candidate_identity,
        "reason": "WRITER_CATEGORY_LOCK_FAILED", "db_error_code": 1205,
    }


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
    journal_factory = Mock()
    monkeypatch.setattr(supply, "OperationalJournal", journal_factory)
    monkeypatch.setattr(supply, "_write", writer)
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    assert supply.run_writer(approved, {"source_id": "other-source", "preview": {}})[
        "status"] == "COMMITTED"
    adapter.verify.assert_called_once_with({}, NOW)
    journal_factory.assert_called_once_with(approved)
    writer.assert_called_once()
    assert writer.call_args.args[0] == approved
    assert writer.call_args.args[1].target == approved.target
    assert writer.call_args.args[2] is journal_factory.return_value
    with pytest.raises(SupplyBlocked):
        approved.source(None)


def test_godot_icon_is_source_scoped_and_written_in_same_transaction(monkeypatch):
    raw = profile_data()
    raw["sources"][0]["scope"] = GODOT_IMAGE_SCOPE
    approved = supply.parse_profile(raw, NOW)
    source = approved.source(REPO)
    assert supply._operational_adapter(source, "collect") is supply.ADAPTERS[REPO]
    assert isinstance(supply._operational_adapter(source, "write"), GodotAdapter)
    verified = GodotAdapter(lambda _: RAW, include_icon=True).verify(candidate(), NOW)
    item = bind_snapshot(verified, policy=supply.VERSION, target=approved.target)
    assert item.thumbnail_url == GODOT_ICON_URL
    assert item.content_digest != snapshot().content_digest
    validate_snapshot_freshness(approved, item, NOW)
    with pytest.raises(SupplyBlocked, match="THUMBNAIL_SCOPE_NOT_APPROVED"):
        validate_snapshot_freshness(profile(), item, NOW)
    with pytest.raises(SupplyBlocked, match="THUMBNAIL_SNAPSHOT_INVALID"):
        validate_snapshot_freshness(
            approved, replace(item, thumbnail_url="https://example.invalid/x"), NOW,
        )
    conn, journal, insert = _mock_writer(monkeypatch)
    assert supply._write(approved, item, journal) == "COMMITTED"
    assert insert.call_args.kwargs["thumbnail_url"] == GODOT_ICON_URL
    conn.commit.assert_called_once()
    assert journal.finish.call_args.args[-1] == "COMMITTED"


def test_image_scope_does_not_update_existing_trend(monkeypatch):
    raw = profile_data()
    raw["sources"][0]["scope"] = GODOT_IMAGE_SCOPE
    approved = supply.parse_profile(raw, NOW)
    item = replace(snapshot(), thumbnail_url=GODOT_ICON_URL)
    conn, journal, insert = _mock_writer(monkeypatch, duplicate="SKIP_EXISTING_RELEASE")
    assert supply._write(approved, item, journal) == "SKIP_EXISTING_RELEASE"
    insert.assert_not_called()
    journal.claim.assert_not_called()
    conn.commit.assert_not_called()


@pytest.mark.integration
@pytest.mark.parametrize("thumbnail", [None, GODOT_ICON_URL])
def test_thumbnail_dml_in_isolated_mariadb(db_session: Session, thumbnail):
    """Shared INSERT persists the optional URL; fixture owns rollback."""
    key = uuid4().hex
    conn = db_session.connection()
    category_id = conn.execute(text(
        "INSERT INTO categories (category_name, sort_order, is_active) "
        "VALUES (:name, 0, 1)"
    ), {"name": f"Thumbnail fixture {key}"}).lastrowid
    item = replace(
        snapshot(), title=f"Thumbnail fixture {key}", normalized_title=key,
        external_id=f"fixture-thumbnail:{key}",
        source_key=sha256(f"ETC:fixture-thumbnail:{key}".encode()).hexdigest(),
        thumbnail_url=thumbnail,
    )
    trend_id = supply.insert_trend_item(
        conn, item, category_id=category_id, collected_at=NOW.replace(tzinfo=None),
        summary=item.summary, is_primary=True, status="ACTIVE", platform="ETC",
        thumbnail_url=thumbnail,
    )
    assert conn.execute(text(
        "SELECT thumbnail_url FROM trends WHERE trend_id = :id"
    ), {"id": trend_id}).scalar_one() == thumbnail
    assert conn.execute(text(
        "SELECT count(*) FROM trend_sources WHERE trend_id = :id"
    ), {"id": trend_id}).scalar_one() == 1
    assert conn.execute(text(
        "SELECT count(*) FROM trend_category_map WHERE trend_id = :id"
    ), {"id": trend_id}).scalar_one() == 1
