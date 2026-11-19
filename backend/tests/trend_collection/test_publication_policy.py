"""AP-3C-1 policy and snapshot checks without DB/AI/network access."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from app.trend_collection.godot_release_collector import REPO, ReleaseEvidence
from app.trend_collection.publication_policy import (
    BATCH_SIZE,
    GODOT_POLICY,
    INTERVAL_SECONDS,
    POLICY_VERSION,
    PROFILE,
    SYNTHETIC_PROFILE,
    build_policy_preview,
    evaluate_release,
    synthetic_fixture_decision,
    verify_release_decision,
    writer_boundary,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview
from scripts.collect_source_first import run_cycles

NOW = datetime(2026, 11, 19, 6, 34, tzinfo=timezone.utc)
EVIDENCE = ReleaseEvidence(
    450611675, "4.8-beta4", NOW - timedelta(hours=8),
    f"https://github.com/{REPO}/releases/tag/4.8-beta4", True,
)


def preview():
    return build_rule_first_preview(EVIDENCE, NOW)


def test_real_policy_stays_deferred():
    result = evaluate_release(EVIDENCE, NOW, preview())
    assert result.decision == "DEFERRED"
    assert result.profile_id == PROFILE
    assert result.policy_version == POLICY_VERSION
    assert result.publish_authorization == "NONE"
    assert "SOURCE_RIGHTS_UNVERIFIED" in result.reason_codes
    assert "ACTIVE_CATEGORY_UNVERIFIED" in result.reason_codes
    assert GODOT_POLICY.ai_transfer == "DENIED"
    assert BATCH_SIZE == 1 and INTERVAL_SECONDS == 21600
    snapshot = result.snapshot
    assert snapshot.is_primary is True
    assert snapshot.target == "UNBOUND_OPERATIONAL"
    assert snapshot.proposed_status == "ACTIVE"
    assert snapshot.source_key == sha256(
        f"ETC:{snapshot.external_id}".encode("utf-8")
    ).hexdigest()
    assert len(snapshot.content_digest) == len(snapshot.evidence_ref) == 64
    assert writer_boundary(result) == "BLOCKED_AP3C1_NO_WRITER_AUTHORITY"


@pytest.mark.parametrize("changes", [
    {"source_rights_verified": True}, {"publish_authorization": "PASS"},
    {"summary": "unverified claim"}, {"title": "changed"},
    {"proposed_source": {"source_url": "https://example.invalid"}},
    {"proposed_category_ref": {"parent_code": "GAME", "child_name": "x"}},
    {"ai_api_calls": False}, {"unknown": True}, {"summary": float("nan")},
])
def test_preview_changes_blocked(changes):
    result = evaluate_release(EVIDENCE, NOW, {**preview(), **changes})
    assert result.decision == "BLOCKED"
    assert result.snapshot is None
    assert result.publish_authorization == "NONE"


@pytest.mark.parametrize("changes", [
    {"release_id": True}, {"url": "https://example.invalid"},
    {"prerelease": False}, {"published_at": NOW + timedelta(seconds=1)},
    {"published_at": NOW.replace(tzinfo=None)},
])
def test_invalid_release_blocked(changes):
    assert evaluate_release(replace(EVIDENCE, **changes), NOW, {}).decision == "BLOCKED"


def test_stale_release_skipped():
    old = replace(EVIDENCE, published_at=NOW - timedelta(days=8))
    assert evaluate_release(old, NOW, {}).decision == "SKIPPED"


def test_snapshot_reprojection_detects_changed_content_and_policy():
    item = preview()
    result = evaluate_release(EVIDENCE, NOW, item)
    assert verify_release_decision(result, EVIDENCE, NOW, item)
    with pytest.raises(FrozenInstanceError):
        result.snapshot.title = "changed"
    changed = replace(result.snapshot, is_primary=False)
    assert changed.content_digest != result.snapshot.content_digest
    for forged in (
        replace(result, snapshot=changed), replace(result, policy_version="other"),
        replace(result, decision="AUTO_ELIGIBLE"),
    ):
        assert not verify_release_decision(forged, EVIDENCE, NOW, item)
        assert writer_boundary(forged) == "BLOCKED_AP3C1_NO_WRITER_AUTHORITY"


def test_fixed_synthetic_fixture_has_no_operational_authority():
    result = synthetic_fixture_decision()
    assert result.decision == "AUTO_ELIGIBLE"
    assert result.profile_id == SYNTHETIC_PROFILE
    assert result.snapshot.target == "ISOLATED_SYNTHETIC_ONLY"
    assert result.snapshot.proposed_status == "HIDDEN"
    assert result.publish_authorization == "NONE"
    assert not verify_release_decision(result, EVIDENCE, NOW, preview())
    for candidate in (result, {"decision": "AUTO_ELIGIBLE"}, None):
        assert writer_boundary(candidate) == "BLOCKED_AP3C1_NO_WRITER_AUTHORITY"


def test_policy_preview_never_exports_snapshot_and_preserves_duplicate():
    rows = []
    assert run_cycles(2, 60, fetch=lambda: EVIDENCE, clock=lambda: NOW,
                      sleep=lambda _: None, emit=rows.append,
                      project=build_policy_preview) == 0
    first, second = map(json.loads, rows)
    candidate = first["candidate"]
    assert candidate["policy_decision"] == "DEFERRED"
    assert candidate["writer_boundary"] == "BLOCKED_AP3C1_NO_WRITER_AUTHORITY"
    assert "snapshot" not in candidate and "content_digest" not in candidate
    assert candidate["ai_api_calls"] == 0
    assert candidate["publish_authorization"] == "NONE"
    assert second["status"] == "DUPLICATE_IN_PROCESS"
    assert all(not row["database_write_performed"] for row in (first, second))
