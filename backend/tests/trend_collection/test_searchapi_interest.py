"""Interest adapter tests use separate fake clients, never external I/O."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.searchapi_interest import (
    SCOPE,
    SOURCE_ID,
    SOURCE_URL,
    SearchInterestAdapter,
)
from app.trend_collection.supply_adapter import ADAPTERS, SupplyBlocked

NOW = datetime(2026, 11, 25, 5, tzinfo=timezone.utc)
TOPICS = {"작품2": ("ENTERTAINMENT", "드라마")}


def _client(*, active=True, query="작품2", categories=None):
    client = Mock()
    client.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now",
            "geo": "KR", "time": "past_24_hours",
        },
        "trends": [{
            "query": query, "start_date": "2026-11-25T03:00:00Z",
            "news_token": "private-token", "is_active": active,
            "categories": categories or ["entertainment"],
        }],
    }
    return client


def _adapter(client):
    return SearchInterestAdapter(client, topics=TOPICS, clock=lambda: NOW)


def test_independent_observation_projects_only_interest():
    collector, writer = _client(), _client()
    preview = _adapter(collector).collect_preview()
    assert preview is not None
    assert "private-token" not in str(preview)
    snapshot = _adapter(writer).verify(preview, NOW + timedelta(seconds=1))
    assert snapshot.title == "작품2"
    assert snapshot.child_name == "드라마"
    assert snapshot.source_url == SOURCE_URL
    assert snapshot.candidate_identity == "searchapi-interest:" + preview["case_key"]
    assert "Google Trends" in snapshot.summary
    assert "공개" not in snapshot.summary
    assert snapshot.target == "UNBOUND_OPERATIONAL"
    assert ADAPTERS[SOURCE_ID].scope == SCOPE
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_ROLE_NOT_BOUND"):
        ADAPTERS[SOURCE_ID].verify(preview, NOW)
    collector.trending_now.assert_called_once()
    writer.trending_now.assert_called_once()
    collector.related_news.assert_not_called()
    writer.related_news.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"active": False}, {"query": "알 수 없는 인물"},
    {"categories": ["food_and_drink"]},
])
def test_unknown_inactive_or_wrong_root_is_not_collected(changes):
    assert _adapter(_client(**changes)).collect_preview() is None


def test_writer_rejects_disappeared_observation():
    preview = _adapter(_client()).collect_preview()
    with pytest.raises(SupplyBlocked, match="INTEREST_OBSERVATION_UNCONFIRMED"):
        _adapter(_client(active=False)).verify(preview, NOW)


def test_forged_category_and_expired_preview_do_not_call_writer():
    preview = _adapter(_client()).collect_preview()
    writer = _client()
    with pytest.raises(SupplyBlocked, match="INTEREST_PREVIEW_INVALID"):
        _adapter(writer).verify({**preview, "child_name": "음악"}, NOW)
    with pytest.raises(SupplyBlocked, match="INTEREST_PREVIEW_EXPIRED"):
        _adapter(writer).verify(preview, NOW + timedelta(minutes=11))
    writer.trending_now.assert_not_called()


def test_freshness_is_bound_to_interest_scope_and_window():
    preview = _adapter(_client()).collect_preview()
    snapshot = _adapter(_client()).verify(preview, NOW)
    profile = SimpleNamespace(
        source=lambda source_id: SimpleNamespace(
            scope=SCOPE if source_id == SOURCE_ID else "WRONG",
        ),
    )
    validate_snapshot_freshness(profile, snapshot, NOW)
    with pytest.raises(SupplyBlocked, match="SOURCE_SNAPSHOT_MISMATCH"):
        validate_snapshot_freshness(
            SimpleNamespace(source=lambda _: SimpleNamespace(scope="NEWS")),
            snapshot, NOW,
        )
    with pytest.raises(SupplyBlocked, match="SOURCE_SNAPSHOT_MISMATCH"):
        validate_snapshot_freshness(
            profile, replace(snapshot, source_url="https://example.org"), NOW,
        )
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_EXPIRED"):
        validate_snapshot_freshness(
            profile,
            replace(snapshot, started_at_utc=(NOW - timedelta(days=2)).isoformat()),
            NOW,
        )
