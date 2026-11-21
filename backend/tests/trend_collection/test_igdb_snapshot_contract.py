"""Snapshot policy/Writer compatibility: no live API, credentials or DML."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.godot_release_collector import REPO
from app.trend_collection.igdb_adapter import IGDB_ID, SOURCE_ID, VISITS_ID
from app.trend_collection.igdb_supply_snapshot import IgdbSnapshotBridge
from app.trend_collection.publication_policy import (
    POLICY_VERSION,
    PROFILE,
    ContentSnapshot,
    PopularitySnapshot,
    _digest,
)
from app.trend_collection.supply_adapter import (
    ADAPTERS,
    SupplyBlocked,
    bind_snapshot,
)
from scripts import run_auto_supply as supply

NOW = datetime(2026, 11, 20, 7, tzinfo=timezone.utc)
STAMP = int((NOW - timedelta(hours=5)).timestamp())


def _approved(source_id, scope):
    def source(identity):
        if identity != source_id:
            raise SupplyBlocked("SOURCE_NOT_APPROVED")
        return SimpleNamespace(scope=scope)
    return SimpleNamespace(source=source, validate_time=lambda _: None)


def _game():
    return {
        "id": 87622, "name": "Free Fire",
        "url": "https://www.igdb.com/games/free-fire",
        "game_type": {"type": "Main Game"},
        "platforms": [{"id": 34, "name": "Android"}],
        "themes": [{"id": 1, "name": "Action"}],
        "age_ratings": [{
            "organization": {"id": 5, "name": "GRAC"},
            "rating_category": {"id": 25, "rating": "15+"},
        }],
    }


def _query(endpoint, body):
    if endpoint == "popularity_types":
        return [{"id": VISITS_ID, "name": "Visits",
                 "external_popularity_source": {"id": IGDB_ID, "name": "IGDB"}}]
    if endpoint == "popularity_primitives":
        return [{"game_id": 87622, "value": 0.002,
                 "popularity_type": VISITS_ID,
                 "external_popularity_source": IGDB_ID,
                 "calculated_at": STAMP}]
    if endpoint == "games":
        assert "87622" in body
        return [_game()]
    raise AssertionError("unexpected endpoint")


def _popularity():
    bridge = IgdbSnapshotBridge(_query)
    from app.trend_collection.igdb_adapter import IgdbReviewAdapter

    preview = IgdbReviewAdapter(_query).collect_review(NOW)
    return bridge.verify(preview, NOW), preview


def test_popularity_snapshot_projection_and_digest():
    snapshot, preview = _popularity()
    assert type(snapshot) is PopularitySnapshot
    assert snapshot.candidate_identity == "igdb-game:87622"
    assert snapshot.rank == 1 and snapshot.metric_id == VISITS_ID
    assert snapshot.source_url == "https://www.igdb.com/games/free-fire"
    assert snapshot.source_key == sha256(b"ETC:igdb-game:87622").hexdigest()
    assert snapshot.content_digest == _digest(asdict(snapshot))
    assert not hasattr(snapshot, "source_published_at")
    assert preview["publish_authorization"] == "NONE"
    assert SOURCE_ID not in ADAPTERS


def test_godot_snapshot_schema_and_digest_remain_unchanged():
    from app.trend_collection.godot_release_collector import _parse
    from app.trend_collection.publication_policy import evaluate_release
    from app.trend_collection.rule_first_preview import build_rule_first_preview

    raw = {"id": 42, "tag_name": "4.8-beta4", "draft": False,
           "prerelease": True,
           "html_url": f"https://github.com/{REPO}/releases/tag/4.8-beta4",
           "published_at": "2026-11-18T22:01:47Z"}
    preview = build_rule_first_preview(_parse(raw), NOW)
    snapshot = evaluate_release(_parse(raw), NOW, preview).snapshot
    assert type(snapshot) is ContentSnapshot
    assert snapshot.content_digest == _digest(asdict(snapshot))
    assert "calculated_at_utc" not in asdict(snapshot)
    assert list(asdict(snapshot)) == [
        "profile_id", "policy_version", "target", "candidate_identity",
        "evidence_ref", "title", "normalized_title", "summary", "source_url",
        "external_id", "source_key", "platform", "parent_code", "child_name",
        "observed_at_utc", "source_published_at", "proposed_status",
        "is_primary", "thumbnail_url", "source_title",
    ]


@pytest.mark.parametrize("hours,minutes,valid", [
    (48, 0, True), (48, 1, False), (0, 0, True),
])
def test_igdb_source_window(hours, minutes, valid):
    snapshot, _ = _popularity()
    snapshot = replace(
        snapshot,
        calculated_at_utc=(NOW - timedelta(hours=hours, minutes=minutes)).isoformat(),
    )
    profile = _approved(SOURCE_ID, "IGDB_VISITS_FACTS_LINK_V1")
    if valid:
        validate_snapshot_freshness(profile, snapshot, NOW)
    else:
        with pytest.raises(SupplyBlocked, match="SNAPSHOT_EXPIRED"):
            validate_snapshot_freshness(profile, snapshot, NOW)


@pytest.mark.parametrize("change", [
    {"rank": 0}, {"metric_id": 2}, {"metric_id": True},
    {"parent_code": "IT_DIGITAL"},
    {"source_url": "https://example.com/games/free-fire"},
    {"external_id": "igdb-game:999"},
    {"source_key": "0" * 64},
])
def test_igdb_source_binding_rejects_forgery(change):
    snapshot, _ = _popularity()
    with pytest.raises(SupplyBlocked, match="SOURCE_SNAPSHOT_MISMATCH"):
        validate_snapshot_freshness(
            _approved(SOURCE_ID, "IGDB_VISITS_FACTS_LINK_V1"),
            replace(snapshot, **change), NOW,
        )


def test_reject_wrong_scope_or_missing_approval():
    snapshot, _ = _popularity()
    for source, scope in ((SOURCE_ID, "WRONG_SCOPE"), (REPO, "GODOT_FACTS_LINK_V1")):
        with pytest.raises(SupplyBlocked):
            validate_snapshot_freshness(_approved(source, scope), snapshot, NOW)


def test_preview_age_boundary_and_future():
    snapshot, _ = _popularity()
    profile = _approved(SOURCE_ID, "IGDB_VISITS_FACTS_LINK_V1")
    validate_snapshot_freshness(
        profile,
        replace(snapshot, observed_at_utc=(NOW - timedelta(minutes=10)).isoformat()),
        NOW,
    )
    for interval in (timedelta(minutes=10, seconds=1), -timedelta(seconds=1)):
        with pytest.raises(SupplyBlocked, match="SNAPSHOT_EXPIRED"):
            validate_snapshot_freshness(
                profile,
                replace(snapshot, observed_at_utc=(NOW - interval).isoformat()),
                NOW,
            )


def test_bind_snapshot_supports_both_concrete_types():
    snapshot, _ = _popularity()
    bound = bind_snapshot(snapshot, policy="AUTO_V1", target="local:test")
    assert type(bound) is PopularitySnapshot
    assert snapshot.target != bound.target
    assert bound.content_digest != snapshot.content_digest


def test_unknown_snapshot_type_cannot_be_persisted():
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_TYPE_NOT_SUPPORTED"):
        validate_snapshot_freshness(_approved(SOURCE_ID, ""), object(), NOW)


def test_writer_duplicate_igdb_url_change_is_hold():
    snapshot, _ = _popularity()
    conn = Mock()
    conn.execute.side_effect = [
        Mock(all=Mock(return_value=[(
            snapshot.external_id, snapshot.source_key,
        )])),
        Mock(all=Mock(return_value=[("https://www.igdb.com/games/changed",)])),
    ]
    with pytest.raises(SupplyBlocked, match="SOURCE_URL_CHANGED"):
        supply.inspect_snapshot(conn, snapshot)
    assert conn.execute.call_count == 2


def test_writer_duplicate_igdb_url_same_is_skip():
    snapshot, _ = _popularity()
    conn = Mock()
    conn.execute.side_effect = [
        Mock(all=Mock(return_value=[(
            snapshot.external_id, snapshot.source_key,
        )])),
        Mock(all=Mock(return_value=[(snapshot.source_url,)])),
    ]
    assert supply.inspect_snapshot(conn, snapshot) == "SKIP_EXISTING_RELEASE"


def test_writer_preconnector_approval_guard(monkeypatch):
    snapshot, _ = _popularity()
    profile = _approved(SOURCE_ID, "IGDB_VISITS_FACTS_LINK_V1")
    monkeypatch.setattr(supply, "_read_profile", lambda: profile)
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    supply._assert_current(profile, replace(
        snapshot, target="local:test", policy_version=supply.VERSION,
    ))
    with pytest.raises(SupplyBlocked):
        supply._assert_current(
            _approved(REPO, "GODOT_FACTS_LINK_V1"), snapshot,
        )


def test_profile_constant_is_compatible():
    assert PROFILE == supply.PROFILE
    assert POLICY_VERSION != supply.VERSION


def test_igdb_bridge_passes_cursor_without_storing_state():
    bridge = IgdbSnapshotBridge(_query)
    bridge._review.collect_review = Mock(return_value=None)
    assert bridge.collect_preview(after_game_id=87622) is None
    args, kwargs = bridge._review.collect_review.call_args
    assert args[0].tzinfo is not None
    assert kwargs == {'after_game_id': 87622}


def test_collector_empty_response_is_explicit_and_does_not_authorize_write(
    monkeypatch,
):
    adapter = Mock()
    adapter.collect_preview.return_value = None
    monkeypatch.setitem(supply.ADAPTERS, SOURCE_ID, adapter)
    source = supply.ApprovedSource(
        source_id=SOURCE_ID, scope="IGDB_VISITS_FACTS_LINK_V1",
        rights_ref="test-only",
    )
    assert supply.collect_envelope(source, after_game_id=87622) == {
        'source_id': SOURCE_ID, 'status': 'NO_ELIGIBLE_CANDIDATE',
    }
    adapter.collect_preview.assert_called_once_with(after_game_id=87622)
    for invalid in (0, True, 10**20, -2):
        with pytest.raises(SupplyBlocked, match="GAME_CURSOR_INVALID"):
            supply.collect_envelope(source, after_game_id=invalid)
    assert adapter.collect_preview.call_count == 1


def test_godot_cannot_report_igdb_no_candidate(monkeypatch):
    adapter = Mock()
    adapter.collect_preview.return_value = None
    monkeypatch.setitem(supply.ADAPTERS, REPO, adapter)
    source = supply.ApprovedSource(
        source_id=REPO, scope="GODOT_FACTS_LINK_V1",
        rights_ref="test-only",
    )
    with pytest.raises(SupplyBlocked, match="SOURCE_PREVIEW_MISSING"):
        supply.collect_envelope(source)
    adapter.collect_preview.assert_called_once_with()


def test_collect_cli_emits_no_candidate_without_db(monkeypatch, capsys):
    import json
    import sys
    from contextlib import nullcontext

    source = supply.ApprovedSource(
        source_id=SOURCE_ID, scope="IGDB_VISITS_FACTS_LINK_V1",
        rights_ref="test-only",
    )
    profile = Mock()
    profile.source.return_value = source
    monkeypatch.setattr(
        supply, "approved_cycle", lambda role: nullcontext(profile),
    )
    collector = Mock(return_value={
        'source_id': SOURCE_ID, 'status': 'NO_ELIGIBLE_CANDIDATE',
    })
    monkeypatch.setattr(supply, "collect_envelope", collector)
    monkeypatch.setattr(sys, "argv", [
        "run_auto_supply", "collect", "--source-id", SOURCE_ID,
        "--after-game-id", "87622",
    ])
    assert supply.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "source_id": SOURCE_ID, "status": "NO_ELIGIBLE_CANDIDATE",
    }
    collector.assert_called_once_with(source, after_game_id=87622)
    profile.validate_time.assert_called_once()
