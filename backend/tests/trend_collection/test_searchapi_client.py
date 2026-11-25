"""HTTP transport contract checks using fake responses, no live API calls."""

import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from app.trend_collection.searchapi_client import (
    MAX_CALLS,
    SearchApiClient,
    SearchApiClientError,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, limit):
        return self.payload[:limit]


def _client():
    opener = Mock()
    opener.open.return_value = FakeResponse({"search_metadata": {"status": "Success"},
                                             "trends": []})
    return SearchApiClient("not-a-real-key", opener=opener), opener


def test_fixed_host_and_bearer_header_only():
    client, opener = _client()
    client.trending_now()
    request = opener.open.call_args.args[0]
    assert request.full_url == (
        "https://www.searchapi.io/api/v1/search?"
        "engine=google_trends_trending_now&geo=KR&time=past_24_hours")
    assert "not-a-real-key" not in request.full_url
    assert request.get_header("Authorization") == "Bearer not-a-real-key"
    assert opener.open.call_args.kwargs["timeout"] == 10


def test_related_news_is_fixed_endpoint():
    client, opener = _client()
    client.related_news("Abc+/=")
    url = opener.open.call_args.args[0].full_url
    assert "engine=google_trends_trending_now_news" in url
    assert "news_token=Abc%2B%2F%3D" in url


def test_request_budget():
    client, opener = _client()
    for _ in range(MAX_CALLS):
        client.trending_now()
    with pytest.raises(SearchApiClientError, match="SEARCHAPI_REQUEST_BUDGET"):
        client.trending_now()
    assert opener.open.call_count == MAX_CALLS


@pytest.mark.parametrize(
    "token", ["", "bad token", "x\n", "https://evil.org", "*" * 100],
)
def test_bad_news_tokens_do_not_trigger_io(token):
    client, opener = _client()
    with pytest.raises(SearchApiClientError, match="SEARCHAPI_NEWS_TOKEN_INVALID"):
        client.related_news(token)
    opener.open.assert_not_called()


def test_empty_error_response_never_accepted():
    client, opener = _client()
    opener.open.return_value = FakeResponse({"error": "unknown"})
    with pytest.raises(SearchApiClientError, match="SEARCHAPI_UNCONFIRMED_RESPONSE"):
        client.trending_now()


def test_official_search_uses_existing_third_call_budget():
    client, opener = _client()
    client.trending_now()
    client.related_news("abc")
    client.official_search("시그널2")
    request = opener.open.call_args.args[0]
    assert parse_qs(urlsplit(request.full_url).query) == {
        "engine": ["google"], "q": ['"시그널2" 공식 발표'],
        "gl": ["kr"], "hl": ["ko"],
    }
    assert request.get_header("Authorization") == "Bearer not-a-real-key"
    with pytest.raises(SearchApiClientError, match="SEARCHAPI_REQUEST_BUDGET"):
        client.official_search("시그널2")
    assert opener.open.call_count == 3
