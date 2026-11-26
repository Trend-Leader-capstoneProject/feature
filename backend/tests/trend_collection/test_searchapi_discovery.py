"""Pure discovery checks; never performs network I/O, DB writes or publication."""

from datetime import datetime, timezone

import pytest

from app.trend_collection.searchapi_discovery import (
    SearchApiDiscoveryError,
    parse_related_news,
    parse_trending_now,
)

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)


def _trends(items):
    return {"search_parameters": {"engine": "google_trends_trending_now",
                                  "geo": "KR", "time": "past_24_hours"},
            "trends": items}


def _trend(**changes):
    value = {"query": "커피 신제품", "start_date": "2026-11-22T10:00:00Z",
             "news_token": "search-token", "categories": ["food_and_drink"],
             "is_active": True}
    return {**value, **changes}


def _news(items):
    return {"search_parameters": {"engine": "google_trends_trending_now_news"},
            "news": items}


def _article(**changes):
    value = {"title": "브랜드 공식 보도", "source": "브랜드",
             "link": "https://example.org/official/release",
             "iso_date": "2026-11-22T10:00:00Z"}
    return {**value, **changes}


def test_food_query_is_only_a_hint_not_verified_category():
    result = parse_trending_now(_trends([_trend()]), now=NOW)
    assert len(result) == 1
    assert result[0].possible_root_codes == frozenset({"FOOD"})
    assert not hasattr(result[0], "category_id")
    assert not hasattr(result[0], "publish_authorization")


def test_beauty_and_fashion_remains_ambiguous():
    item = _trend(categories=["beauty_and_fashion"])
    assert parse_trending_now(_trends([item]), now=NOW)[0].possible_root_codes == (
        frozenset({"BEAUTY", "FASHION"}))


def test_out_of_scope_filtered_but_inactive_24h_signal_retained():
    items = [_trend(categories=["other"]), _trend(is_active=False),
             _trend(categories=["food_and_drink", "politics"])]
    result = parse_trending_now(_trends(items), now=NOW)
    assert len(result) == 1
    assert result[0].is_active is False
    assert result[0].possible_root_codes == frozenset({"FOOD"})


def test_deduplication_and_bound():
    items = [_trend(query=f"키워드{i}") for i in range(35)]
    items.insert(1, _trend(query="키워드0"))
    assert len(parse_trending_now(_trends(items), now=NOW)) == 20


@pytest.mark.parametrize("bad", [
    None, {}, _trends({}),
    {**_trends([]), "search_parameters": {
        "engine": "google_trends_trending_now",
        "geo": "US", "time": "past_24_hours",
    }},
])
def test_bad_trend_contract_rejected(bad):
    with pytest.raises(SearchApiDiscoveryError):
        parse_trending_now(bad, now=NOW)


def test_invalid_trend_values_filtered():
    items = [_trend(query="bad\x00"), _trend(start_date="2026-11-22"),
             _trend(start_date="2027-01-01T00:00:00Z"),
             _trend(news_token=None)]
    assert not parse_trending_now(_trends(items), now=NOW)


def test_news_metadata_is_not_publication_authorization():
    article = parse_related_news(_news([_article()]), now=NOW)[0]
    assert article.url == "https://example.org/official/release"
    assert not hasattr(article, "publication_status")
    assert not hasattr(article, "verified_content")


@pytest.mark.parametrize("link", [
    "http://example.org/a", "https://127.0.0.1/a", "https://localhost/a",
    "https://example.local/a", "https://user:pass@example.com/a",
    "https://example.org:8080/a", "https://example.org/a#fragment",
    "https://[::1]/a", "https://example.org/a\n",
])
def test_untrusted_article_link_filtered(link):
    assert not parse_related_news(_news([_article(link=link)]), now=NOW)


def test_news_no_extra_identical_urls():
    assert len(parse_related_news(_news([_article(), _article()]), now=NOW)) == 1


def test_news_wrong_engine_rejected():
    with pytest.raises(SearchApiDiscoveryError):
        parse_related_news(
            {**_news([]), "search_parameters": {"engine": "other"}}, now=NOW,
        )
