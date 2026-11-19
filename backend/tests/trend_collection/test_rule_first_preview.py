"""Rule-first metadata replay and rejection; no external requests."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.trend_collection.godot_release_collector import (
    REPO,
    CollectionError,
    ReleaseEvidence,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview
from scripts.collect_source_first import run_cycles

NOW = datetime(2026, 11, 19, 4, 6, tzinfo=timezone.utc)
EVIDENCE = ReleaseEvidence(
    123, "4.8-beta4", NOW - timedelta(hours=1),
    f"https://github.com/{REPO}/releases/tag/4.8-beta4", True,
)


@pytest.mark.parametrize("tag,prerelease,label", [
    ("4.8-stable", False, "정식"),
    ("4.8-beta4", True, "beta4"),
    ("4.8-rc1", True, "rc1"),
    ("4.8-dev2", True, "dev2"),
])
def test_rule_preview_is_fact_only(tag, prerelease, label):
    evidence = replace(EVIDENCE, tag=tag, prerelease=prerelease,
                       url=f"https://github.com/{REPO}/releases/tag/{tag}")
    result = build_rule_first_preview(evidence, NOW)
    assert result["summary"] == f"Godot 4.8 {label} 버전이 공개되었습니다."
    assert result["ai_api_calls"] == 0
    assert result["analysis_status"] == "RULE_BASED_PREVIEW"
    assert result["source_rights_verified"] is False
    assert result["popularity_verified"] is False
    assert result["publication_status"] == "NOT_FOR_PUBLICATION"
    assert result["publish_authorization"] == "NONE"
    assert result["proposed_source"]["source_url"] == evidence.url
    assert result["proposed_category_ref"]["parent_code"] == "IT_DIGITAL"
    assert result["thumbnail_url"] is None


@pytest.mark.parametrize("changes", [
    {"release_id": True}, {"release_id": 0}, {"release_id": 10**20},
    {"tag": "unrecognized"}, {"prerelease": False},
    {"url": "https://example.invalid/release"},
    {"published_at": NOW.replace(tzinfo=None)},
    {"published_at": NOW + timedelta(seconds=1)},
    {"published_at": NOW - timedelta(days=8)},
])
def test_inconsistent_evidence_held(changes):
    with pytest.raises(CollectionError):
        build_rule_first_preview(replace(EVIDENCE, **changes), NOW)


def test_naive_observation_is_held():
    with pytest.raises(CollectionError, match="RULE_TIMEZONE_REQUIRED"):
        build_rule_first_preview(EVIDENCE, NOW.replace(tzinfo=None))


def test_rule_projection_preserves_loop_hold_and_duplicate():
    outputs = []
    records = iter([EVIDENCE, replace(EVIDENCE, prerelease=False), EVIDENCE])
    result = run_cycles(3, 60, fetch=lambda: next(records), clock=lambda: NOW,
                        sleep=lambda _: None, emit=outputs.append,
                        project=build_rule_first_preview)
    rows = [json.loads(row) for row in outputs]
    assert [row["status"] for row in rows] == [
        "NEW_PREVIEW_ONLY", "HOLD", "DUPLICATE_IN_PROCESS",
    ]
    assert rows[0]["candidate"]["ai_api_calls"] == 0
    assert all(row["database_write_performed"] is False for row in rows)
    assert all(row["publish_authorization"] == "NONE" for row in rows)
    assert result == 2
