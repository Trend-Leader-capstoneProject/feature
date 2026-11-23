"""Saved SearchApi response audit tests. No real network or database."""

import json
from datetime import date, datetime, timezone

import pytest

from app.trend_collection.searchapi_discovery import (
    parse_trending_now,
    summarize_trend_response,
)
from scripts.audit_searchapi_history import (
    HistoryReadBlocked,
    _safe_result_url,
    _select_history_entry,
    recover_history,
)

NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
SEARCH_ID = "search_ABC123"
RESULT_URL = "https://www.searchapi.io/api/v1/public_search/search_ABC123.json"


def saved_payload():
    return {
        "search_metadata": {"id": SEARCH_ID, "status": "Success"},
        "search_parameters": {"engine": "google_trends_trending_now",
                              "geo": "KR", "time": "past_24_hours"},
        "trends": [
            {"query": "음식", "categories": ["food_and_drink"],
             "news_token": "SECRET_NEWS_TOKEN", "is_active": True,
             "start_date": "2026-11-23T10:00:00Z"},
            {"query": "게임", "categories": ["games"],
             "news_token": "SECRET_GAME_TOKEN", "is_active": False,
             "start_date": "2026-11-23T10:00:00Z"},
            {"query": "사건", "categories": ["other"],
             "news_token": "SECRET_OTHER_TOKEN", "is_active": True,
             "start_date": "2026-11-23T10:00:00Z"},
            {"query": "IT", "categories": ["technology"],
             "news_token": "SECRET_TECH_TOKEN", "is_active": True,
             "start_date": "2026-11-23T10:00:00Z"},
        ],
    }


def history_payload():
    return {"searches": [{"id": SEARCH_ID,
                          "engine": "google_trends_trending_now",
                          "params": {"geo": "KR", "time": "past_24_hours"},
                          "status": "Success",
                          "created_at": "2026-11-23T10:00:00Z",
                          "json_url": RESULT_URL}]}


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, count):
        return self.payload[:count]


class FakeOpener:
    def __init__(self, *, corrupted_id=False):
        self.calls = []
        self.corrupted_id = corrupted_id

    def open(self, req, timeout):
        self.calls.append((req.full_url, req.headers.copy(), timeout))
        if "search_history" in req.full_url:
            return FakeResponse(history_payload())
        if req.full_url == RESULT_URL:
            payload = saved_payload()
            if self.corrupted_id:
                payload["search_metadata"]["id"] = "search_BAD"
            return FakeResponse(payload)
        raise AssertionError("unexpected network endpoint")


def test_recover_only_saved_results_without_search_or_secret_output():
    opener = FakeOpener()
    report = recover_history("PLACEHOLDER_KEY", day=date(2026, 11, 23),
                             opener=opener)
    assert report["new_trending_searches"] == 0
    assert report["history_reads"] == 2
    assert report["raw_total"] == 4
    assert report["upstream_category_counts"]["other"] == 1
    assert report["state_counts"]["inactive"] == 1
    assert report["mapped_eligible_count"] == 3
    assert {x["query"] for x in report["eligible_leads"]} == {
        "음식", "게임", "IT",
    }
    assert "PLACEHOLDER_KEY" not in str(report)
    assert "SECRET_NEWS_TOKEN" not in str(report)
    assert RESULT_URL not in str(report)
    assert len(opener.calls) == 2
    assert "search_history?" in opener.calls[0][0]
    assert opener.calls[0][1].get("Authorization") == "Bearer PLACEHOLDER_KEY"
    assert opener.calls[1][1].get("Authorization") is None


@pytest.mark.parametrize("bad", [
    "https://evil.example/api/v1/public_search/search_ABC123.json",
    "http://www.searchapi.io/api/v1/public_search/search_ABC123.json",
    "https://www.searchapi.io.evil.example/api/v1/public_search/search_ABC123.json",
    "https://www.searchapi.io@evil.example/api/v1/public_search/search_ABC123.json",
    "https://www.searchapi.io/api/v1/public_search/search_ABC123.json?api_key=SECRET",
    "https://www.searchapi.io/api/v1/public_search/search_ABC123.json#fragment",
    "https://www.searchapi.io:8443/api/v1/public_search/search_ABC123.json",
    "https://www.searchapi.io/api/v1/public_search/../../secrets",
])
def test_reject_unsafe_saved_result_urls(bad):
    with pytest.raises(HistoryReadBlocked, match="UNSAFE_HISTORY_RESULT_URL"):
        _safe_result_url(bad)


def test_history_multiple_matches_fail_closed():
    data = history_payload()
    data["searches"].append(dict(data["searches"][0]))
    with pytest.raises(HistoryReadBlocked, match="HISTORY_NO_UNIQUE_KR_TREND_RESULT"):
        _select_history_entry(data, date(2026, 11, 23))


def test_mismatched_saved_response_id_is_rejected():
    with pytest.raises(HistoryReadBlocked, match="HISTORY_RESULT_ID_MISMATCH"):
        recover_history("PLACEHOLDER_KEY", day=date(2026, 11, 23),
                        opener=FakeOpener(corrupted_id=True))


def test_inactive_and_technology_and_games_are_reviewable():
    leads = parse_trending_now(saved_payload(), now=NOW)
    assert len(leads) == 3
    assert [x.is_active for x in leads] == [True, False, True]
    assert leads[1].possible_root_codes == frozenset({"GAME"})
    assert leads[2].possible_root_codes == frozenset({"IT_DIGITAL"})


def test_raw_category_summary_does_not_hide_excluded_categories():
    summary = summarize_trend_response(saved_payload(), now=NOW)
    assert summary["raw_total"] == 4
    assert summary["upstream_category_counts"]["other"] == 1
    assert summary["mapped_eligible_count"] == 3
    assert "SECRET" not in str(summary)
