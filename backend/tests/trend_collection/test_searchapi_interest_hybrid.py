"""Hybrid classification and independent verification with fake clients."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.trend_collection.searchapi_interest import SearchInterestAdapter
from app.trend_collection.supply_adapter import SupplyBlocked
from scripts.auto_supply_control import INTEREST_SOURCE_ID, next_state

NOW = datetime(2026, 11, 28, 5, tzinfo=timezone.utc)
TOPICS = {"작품2": ("ENTERTAINMENT", "드라마")}


def item(query, hint, *, active=True):
    return {
        "query": query, "start_date": "2026-11-28T03:00:00Z",
        "is_active": active, "categories": [hint],
    }


def adapter(items, *, hybrid=True, topics=TOPICS):
    client = Mock()
    client.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now", "geo": "KR",
            "time": "past_24_hours",
        },
        "trends": items,
    }
    return SearchInterestAdapter(
        client, topics=topics, hybrid=hybrid, clock=lambda: NOW,
    ), client


@pytest.mark.parametrize("query,hint,expected", [
    ("작품2", "entertainment", ("ENTERTAINMENT", "드라마")),
    ("스웨이드 재킷", "beauty_and_fashion", ("FASHION", "의류")),
    ("신제품 립틴트", "beauty_and_fashion", ("BEAUTY", "메이크업")),
    ("패션 브랜드 향수 협업", "beauty_and_fashion", ("BEAUTY", "향수")),
    ("뷰티 신제품", "beauty_and_fashion", ("BEAUTY", "기타")),
    ("신제품 초콜릿 디저트", "food_and_drink", ("FOOD", "기타")),
    ("영화 향수", "entertainment", ("ENTERTAINMENT", "영화")),
    ("신작 웹툰", "entertainment", ("ENTERTAINMENT", "웹툰·애니메이션")),
])
def test_independent_hybrid(query, hint, expected):
    collector, cc = adapter([item(query, hint)])
    writer, wc = adapter([item(query, hint)])
    preview = json.loads(json.dumps(collector.collect_preview()))
    snapshot = writer.verify(preview, NOW + timedelta(seconds=1))
    assert (snapshot.parent_code, snapshot.child_name) == expected
    cc.trending_now.assert_called_once()
    wc.trending_now.assert_called_once()
    cc.related_news.assert_not_called()
    wc.related_news.assert_not_called()
    wc.official_search.assert_not_called()


@pytest.mark.parametrize("query,hint", [
    ("고향에 대한 향수", "beauty_and_fashion"),
    ("유명인 향수 사생활 논란", "beauty_and_fashion"),
    ("미확인 브랜드", "beauty_and_fashion"),
    ("향수 재킷", "beauty_and_fashion"),
    ("신제품 러닝화", "entertainment"),
    ("신작 웹툰", "games"),
])
def test_unconfirmed_candidates_excluded(query, hint):
    collector, _ = adapter([item(query, hint)])
    assert collector.collect_preview() is None


def test_filter_before_limit_and_rotate():
    inactive = [item(f"비활성{i}", "entertainment", active=False) for i in range(21)]
    items = inactive + [
        item("신제품 러닝화", "beauty_and_fashion"),
        item("립틴트", "beauty_and_fashion"),
    ]
    collector, _ = adapter(items)
    first = collector.collect_preview()
    assert first["query"] == "신제품 러닝화"
    second = collector.collect_preview(after_case_key=first["case_key"])
    assert second["query"] == "립틴트"
    assert collector.diagnostics["eligible"] == 2


def test_writer_rejects_forged_classification_and_changed_policy():
    items = [item("립틴트", "beauty_and_fashion")]
    collector, _ = adapter(items)
    preview = collector.collect_preview()
    writer, _ = adapter(items)
    forged = {
        **preview,
        "classification": {**preview["classification"], "child_name": "기타"},
    }
    with pytest.raises(SupplyBlocked):
        writer.verify(forged, NOW)
    changed, client = adapter(
        items, topics={**TOPICS, "립틴트": ("BEAUTY", "메이크업")},
    )
    with pytest.raises(SupplyBlocked):
        changed.verify(preview, NOW)
    client.trending_now.assert_not_called()


def test_cursor_only_advances_on_confirmed_terminal_result():
    old = {"pending": False, "not_before": 0, "rate_failures": 0,
           "interest_last_case_key": "a" * 64}
    kwargs = {"writer": True, "source_id": INTEREST_SOURCE_ID, "case_key": "b" * 64}
    assert next_state(
        {"status": "HOLD"}, 10, old, **kwargs,
    )["interest_last_case_key"] == "a" * 64
    assert next_state(
        {"status": "SKIP_EXISTING_RELEASE"}, 10, old, **kwargs,
    )["interest_last_case_key"] == "b" * 64
