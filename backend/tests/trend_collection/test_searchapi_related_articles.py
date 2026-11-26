"""Pure article selection and optional request behavior; no live API calls."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import Mock

import pytest

from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.searchapi_client import SearchApiClientError
from app.trend_collection.searchapi_discovery import TrendingLead
from app.trend_collection.searchapi_related_articles import (
    ArticleLinkRule,
    fetch_related_articles,
    select_related_articles,
)

NOW = datetime(2026, 11, 25, 5, tzinfo=timezone.utc)
LEAD = TrendingLead(
    "작품 2", NOW - timedelta(hours=1), "private-token",
    frozenset({"ENTERTAINMENT"}),
)
A = ArticleLinkRule("a.example.com", "/article/", "A", "fixture-rights-a")
B = ArticleLinkRule("b.example.com", "/article/", "B", "fixture-rights-b")


def _item(path="1", *, host="a.example.com", publisher="A", **changes):
    return {
        "title": "작품2 관련 소식", "source": publisher,
        "link": f"https://{host}/article/{path}",
        "iso_date": (NOW - timedelta(hours=1)).isoformat(),
        **changes,
    }


def _payload(*items, token=LEAD.news_token):
    return {
        "search_parameters": {
            "engine": "google_trends_trending_now_news", "news_token": token,
        },
        "news": list(items),
    }


def _select(*items, rules=(A, B)):
    return select_related_articles(
        _payload(*items), lead=LEAD, now=NOW, rules=rules,
    )


def test_prefers_distinct_publisher_and_omits_titles_by_default():
    rows = _select(_item(), _item("2"), _item(host=B.host, publisher="B"))
    assert [r.publisher for r in rows] == ["A", "B"]
    assert [r.selection_order for r in rows] == [1, 2]
    assert all(r.title is None for r in rows)
    assert rows[0].url_key == sha256(rows[0].url.encode()).hexdigest()
    assert LEAD.news_token not in repr(rows)


def test_one_publisher_can_supply_two_distinct_links():
    rows = _select(_item(), _item(), _item("2"), _item("3"))
    assert [r.url for r in rows] == [
        "https://a.example.com/article/1", "https://a.example.com/article/2",
    ]


def test_title_requires_separate_permission():
    rows = _select(_item(), rules=(replace(A, allow_title=True),))
    assert rows[0].title == "작품2 관련 소식"


@pytest.mark.parametrize("url", [
    "http://a.example.com/article/1",
    "https://a.example.com.evil.test/article/1",
    "https://a.example.com@evil.test/article/1",
    "https://a.example.com:444/article/1",
    "https://a.example.com/article/../redirect",
    "https://a.example.com/article/%2e%2e/1",
    "https://a.example.com/article/1?next=evil",
    "https://a.example.com/article/1#fragment",
    "https://a.example.com/article/redirect/1",
    "https://a.example.com/other/1",
    "https://127.0.0.1/article/1",
])
def test_unsafe_or_out_of_scope_link_is_excluded(url):
    assert _select(_item(link=url)) == ()


def test_canonical_url_deduplicates_default_port():
    rows = _select(_item(), _item(link="https://A.example.com:443/article/1"))
    assert len(rows) == 1
    assert rows[0].url == "https://a.example.com/article/1"


@pytest.mark.parametrize("changes", [
    {"source": "Unapproved publisher"},
    {"title": "다른 작품 관련 소식"},
    {"iso_date": (NOW - timedelta(hours=48)).isoformat()},
    {"iso_date": (NOW + timedelta(seconds=1)).isoformat()},
])
def test_publisher_relevance_and_time_are_required(changes):
    assert _select({**_item(), **changes}) == ()


def test_empty_or_ambiguous_rules_fail_closed():
    assert _select(_item(), rules=()) == ()
    assert _select(_item(), rules=(A, replace(A, allow_title=True))) == ()
    assert _select(_item(), rules=(replace(A, evidence_ref=""),)) == ()


def test_no_approval_does_not_request_news():
    client = Mock()
    result = fetch_related_articles(client, lead=LEAD, now=NOW)
    assert result.status == "DISABLED"
    client.related_news.assert_not_called()


def test_verified_token_is_used_once():
    client = Mock()
    client.related_news.return_value = _payload(_item())
    result = fetch_related_articles(client, lead=LEAD, now=NOW, rules=(A,))
    assert result.status == "AVAILABLE"
    assert len(result.articles) == 1
    client.related_news.assert_called_once_with(LEAD.news_token)


@pytest.mark.parametrize("response", [
    _payload(_item(), token="wrong"),
    {"news": []},
])
def test_unconfirmed_response_falls_back(response):
    client = Mock()
    client.related_news.return_value = response
    result = fetch_related_articles(client, lead=LEAD, now=NOW, rules=(A,))
    assert result.status == "UNAVAILABLE"
    assert result.articles == ()
    client.related_news.assert_called_once()


def test_empty_news_falls_back():
    client = Mock()
    client.related_news.return_value = _payload()
    result = fetch_related_articles(client, lead=LEAD, now=NOW, rules=(A,))
    assert result.status == "EMPTY"
    assert result.articles == ()
    client.related_news.assert_called_once()


def test_network_failure_falls_back_without_retry():
    client = Mock()
    client.related_news.side_effect = SearchApiClientError("SEARCHAPI_NETWORK_ERROR")
    result = fetch_related_articles(client, lead=LEAD, now=NOW, rules=(A,))
    assert result.status == "UNAVAILABLE"
    assert result.articles == ()
    client.related_news.assert_called_once()


@pytest.mark.parametrize("deadline", [1795585962, None])
def test_rate_limit_retains_deadline_and_never_retries(deadline):
    client = Mock()
    client.related_news.side_effect = RateLimited(deadline)
    result = fetch_related_articles(client, lead=LEAD, now=NOW, rules=(A,))
    assert result.status == "RATE_LIMITED"
    assert result.retry_not_before == deadline
    assert result.articles == ()
    client.related_news.assert_called_once()
