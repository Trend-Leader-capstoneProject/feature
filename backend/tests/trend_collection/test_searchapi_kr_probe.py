"""No key, network, DB or file writes in probe tests."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.trend_collection.searchapi_discovery import TrendingLead
from scripts.probe_searchapi_kr import choose_news_leads, collect_report, main

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)


def _lead(query, roots):
    return TrendingLead(query, NOW, "a-token", frozenset(roots))


def test_unambiguous_food_and_entertainment_prioritized():
    leads = (_lead("ambiguous", ("BEAUTY", "FASHION")),
             _lead("movie", ("ENTERTAINMENT",)),
             _lead("food", ("FOOD",)))
    assert [row.query for row in choose_news_leads(leads)] == ["food", "movie"]


def test_empty_and_single_candidate():
    assert choose_news_leads(()) == ()
    assert len(choose_news_leads((_lead("food", ("FOOD",)),))) == 1


def test_lead_limit_is_two():
    leads = tuple(_lead(str(i), ("FOOD",)) for i in range(20))
    assert len(choose_news_leads(leads)) == 2


def test_zero_leads_consumes_only_trending_call():
    client = Mock()
    client.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now",
            "geo": "KR", "time": "past_24_hours",
        },
        "trends": [],
    }
    result = collect_report(client, now=NOW)
    assert result["status"] == "READ_ONLY_DISCOVERY"
    assert result["publication_authorization"] == "NONE"
    assert result["requests_executed"] == 1
    client.related_news.assert_not_called()


def test_two_leads_make_at_most_three_calls_without_publication():
    client = Mock()
    client.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now",
            "geo": "KR", "time": "past_24_hours",
        },
        "trends": [
            {"query": "식품", "start_date": "2026-11-22T11:00:00Z",
             "news_token": "abc", "is_active": True,
             "categories": ["food_and_drink"]},
            {"query": "음악", "start_date": "2026-11-22T11:00:00Z",
             "news_token": "def", "is_active": True,
             "categories": ["entertainment"]},
        ],
    }
    client.related_news.side_effect = lambda token: {
        "search_parameters": {
            "engine": "google_trends_trending_now_news",
            "news_token": token,
        },
        "news": [{"title": "공식 발표", "source": "Official Source",
                  "link": "https://example.org/official",
                  "iso_date": "2026-11-22T11:00:00Z"}],
    }
    result = collect_report(client, now=NOW)
    assert result["requests_executed"] == 3
    assert result["news_queries"] == 2
    assert client.related_news.call_count == 2
    assert all(
        "news_metadata_unverified" in item for item in result["candidates"]
    )


def test_no_flag_never_requests_credentials():
    with pytest.raises(SystemExit):
        main([])

def test_mismatched_news_token_rejected():
    from app.trend_collection.searchapi_discovery import SearchApiDiscoveryError

    client = Mock()
    client.trending_now.return_value = {
        "search_parameters": {"engine": "google_trends_trending_now",
                              "geo": "KR", "time": "past_24_hours"},
        "trends": [{"query": "식품", "start_date": "2026-11-22T11:00:00Z",
                    "news_token": "expected", "is_active": True,
                    "categories": ["food_and_drink"]}],
    }
    client.related_news.return_value = {
        "search_parameters": {"engine": "google_trends_trending_now_news",
                              "news_token": "other"},
        "news": [],
    }
    with pytest.raises(SearchApiDiscoveryError, match="NEWS_TOKEN_MISMATCH"):
        collect_report(client, now=NOW)
