"""Observed metadata replay + explicit failures; no real HTTP or DB."""

import json
import socket
from datetime import datetime, timezone

import pytest

from app.trend_collection.godot_release_collector import (
    RELEASES,
    CollectionError,
    _network_code,
    build_candidate,
    collect,
)
from scripts.collect_source_first import run_cycles

RECORD = {
    "id": 450611675, "tag_name": "4.8-beta4",
    "published_at": "2026-11-18T22:01:47Z",
    "html_url": "https://github.com/godotengine/godot-builds/releases/tag/4.8-beta4",
    "draft": False, "prerelease": True,
}
NOW = datetime(2026, 11, 19, 4, 6, tzinfo=timezone.utc)


def observed(endpoint):
    if endpoint == RELEASES + "?per_page=3":
        return [RECORD]
    assert endpoint == RELEASES + "/450611675"
    return RECORD


def test_candidate_reuses_normalization():
    item = build_candidate(collect(request_json=observed), NOW)
    assert item["normalized_title"] == "godot 4.8 beta4 공개"
    assert item["proposed_category_ref"]["child_name"] == "소프트웨어·앱"
    assert item["proposed_source"]["source_url"] == RECORD["html_url"]
    assert item["publish_authorization"] == "NONE"
    assert item["popularity_verified"] is False


def test_changed_detail_is_held():
    def request(endpoint):
        return [RECORD] if endpoint.endswith("?per_page=3") else {**RECORD, "id": 99}
    with pytest.raises(CollectionError, match="LIST_DETAIL_MISMATCH"):
        collect(request_json=request)


def test_stale_and_wrong_url_held():
    with pytest.raises(CollectionError, match="OUTSIDE_PROPOSED_7_DAY_WINDOW"):
        build_candidate(collect(request_json=observed), NOW.replace(day=29))
    with pytest.raises(CollectionError, match="URL_MISMATCH"):
        collect(request_json=lambda _: [
            {**RECORD, "html_url": "https://example.com"}
        ])


def test_repeat_and_recovery():
    outputs, delays = [], []
    current = iter([None, "error", None])

    def fetch():
        if next(current) == "error":
            raise CollectionError("DNS_RESOLUTION_ERROR")
        return collect(request_json=observed)

    code = run_cycles(3, 60, fetch=fetch, clock=lambda: NOW,
                      sleep=delays.append, emit=outputs.append)
    rows = [json.loads(row) for row in outputs]
    assert [row["status"] for row in rows] == [
        "NEW_PREVIEW_ONLY", "HOLD", "DUPLICATE_IN_PROCESS",
    ]
    assert rows[1]["reason"] == "DNS_RESOLUTION_ERROR"
    assert all(row["database_write_performed"] is False for row in rows)
    assert delays == [60, 60] and code == 2


def test_network_classification():
    assert _network_code(socket.gaierror(-3, "test")) == "DNS_RESOLUTION_ERROR"
    assert _network_code(TimeoutError()) == "TIMEOUT"
