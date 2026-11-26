"""Bounded fixed-endpoint SearchApi client; no credentials persistence."""

import json
from http.client import HTTPException
from string import ascii_letters, digits
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.rate_limit import retry_deadline
from app.trend_collection.searchapi_discovery import official_search_query

ENDPOINT = "https://www.searchapi.io/api/v1/search"
TIMEOUT = 10
MAX_BYTES = 512_000
MAX_CALLS = 3  # Trending + up to two News, or Trending + News + Google.
_TOKEN_ALPHABET = frozenset(ascii_letters + digits + "-_+/=")


class SearchApiClientError(RuntimeError):
    """Stable, credential-free diagnostic codes."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SearchApiClientError("SEARCHAPI_REDIRECT_BLOCKED")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError("non-finite JSON value")


class SearchApiClient:
    """Caller injects a role-scoped key; this client cannot authorize publication."""

    def __init__(self, api_key: str, *, opener=None, wall_clock=None):
        if (not isinstance(api_key, str) or not 1 <= len(api_key) <= 512
                or any(not 33 <= ord(char) <= 126 for char in api_key)):
            raise SearchApiClientError("SEARCHAPI_KEY_INVALID")
        self._key = api_key
        self._opener = opener if opener is not None else build_opener(
            ProxyHandler({}), _NoRedirect(),
        )
        if wall_clock is None:
            from time import time
            wall_clock = time
        self._clock = wall_clock
        self._calls = 0

    def _get(self, *, engine: str, **params) -> dict:
        if self._calls >= MAX_CALLS:
            raise SearchApiClientError("SEARCHAPI_REQUEST_BUDGET")
        self._calls += 1
        query = urlencode({"engine": engine, **params})
        request = Request(
            f"{ENDPOINT}?{query}",
            headers={"Authorization": f"Bearer {self._key}",
                     "Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise SearchApiClientError("SEARCHAPI_UNEXPECTED_STATUS")
                raw = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            try:
                if exc.code == 429:
                    raise RateLimited(retry_deadline(
                        exc.headers or {}, self._clock(),
                    )) from None
                raise SearchApiClientError(f"SEARCHAPI_HTTP_{exc.code}") from None
            finally:
                exc.close()
        except (URLError, OSError, HTTPException):
            raise SearchApiClientError("SEARCHAPI_NETWORK_ERROR") from None
        if len(raw) > MAX_BYTES:
            raise SearchApiClientError("SEARCHAPI_RESPONSE_TOO_LARGE")
        try:
            payload = json.loads(
                raw, object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (UnicodeError, ValueError, RecursionError):
            raise SearchApiClientError("SEARCHAPI_INVALID_JSON") from None
        if not isinstance(payload, dict):
            raise SearchApiClientError("SEARCHAPI_INVALID_JSON")
        metadata = payload.get("search_metadata")
        if not isinstance(metadata, dict) or metadata.get("status") != "Success":
            raise SearchApiClientError("SEARCHAPI_UNCONFIRMED_RESPONSE")
        return payload

    def trending_now(self) -> dict:
        return self._get(engine="google_trends_trending_now",
                         geo="KR", time="past_24_hours")

    def related_news(self, news_token: str) -> dict:
        if (not isinstance(news_token, str)
                or not 1 <= len(news_token) <= 2048
                or any(char not in _TOKEN_ALPHABET for char in news_token)):
            raise SearchApiClientError("SEARCHAPI_NEWS_TOKEN_INVALID")
        return self._get(engine="google_trends_trending_now_news",
                         news_token=news_token)


    def official_search(self, topic: str) -> dict:
        """Find possible official links; results are not verified sources."""
        return self._get(
            engine="google", q=official_search_query(topic), gl="kr", hl="ko",
        )
