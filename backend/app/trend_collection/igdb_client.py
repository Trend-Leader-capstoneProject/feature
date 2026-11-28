"""Bounded IGDB HTTP client for one review cycle, without publication authority."""

import json
import re
import time
from http.client import HTTPException
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.trend_collection.godot_release_collector import CollectionError, RateLimited
from app.trend_collection.igdb_adapter import (
    GAME_FIELDS,
    GAME_IMAGE_FIELDS,
    LIMIT,
    POPULARITY_QUERY,
    TYPE_QUERY,
)
from app.trend_collection.rate_limit import retry_deadline

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
API_BASE = "https://api.igdb.com/v4/"
TIMEOUT = 10
MAX_BYTES = 2_000_000
AUTH_MAX_BYTES = 16_384
MIN_INTERVAL = 0.5
EXPIRY_MARGIN = 60
VALIDATION_INTERVAL = 3600
MAX_QUERIES = 3
MAX_ISSUES = 2
MAX_REQUESTS = 8
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._~+/-]+={0,2}")
GAME_QUERY = re.compile(
    re.escape(f"fields {GAME_FIELDS}; where id = (")
    + r"([1-9][0-9]{0,19}(?:,[1-9][0-9]{0,19}){0,19})\); limit ([1-9][0-9]?);"
)

IMAGE_GAME_QUERY = re.compile(
    re.escape(f"fields {GAME_IMAGE_FIELDS}; where id = (")
    + r"([1-9][0-9]{0,19}(?:,[1-9][0-9]{0,19}){0,19})\); limit ([1-9][0-9]?);"
)


class IgdbClientError(CollectionError):
    """Bounded diagnostic without upstream messages or credential values."""


class _Unauthorized(IgdbClientError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise IgdbClientError("IGDB_REDIRECT_BLOCKED")

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _validate_query(endpoint, body, *, include_cover=False):
    if not isinstance(endpoint, str) or not isinstance(body, str):
        raise IgdbClientError("IGDB_QUERY_NOT_ALLOWED")
    if endpoint == "popularity_types" and body == TYPE_QUERY:
        return
    if endpoint == "popularity_primitives" and body == POPULARITY_QUERY:
        return
    if endpoint == "games" and len(body) <= 2048:
        match = GAME_QUERY.fullmatch(body)
        if match is None and include_cover:
            match = IMAGE_GAME_QUERY.fullmatch(body)
        if match:
            ids = match[1].split(",")
            if len(ids) == len(set(ids)) == int(match[2]) <= LIMIT:
                return
    raise IgdbClientError("IGDB_QUERY_NOT_ALLOWED")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError("non-finite JSON constant")


def _ttl(value):
    if type(value) is not int or not EXPIRY_MARGIN < value <= 2**31 - 1:
        raise IgdbClientError("IGDB_TOKEN_EXPIRY_INVALID")
    return value


class IgdbClient:
    """One principal, one cycle; credentials and token remain in process memory.

    Caller supplies the credentials. No environment lookup, disk cache, DB,
    operational registration, or automatic approval is performed here.
    """

    def __init__(self, client_id, client_secret, *, opener=None,
                 monotonic=time.monotonic, wall_clock=time.time, sleep=time.sleep,
                 include_cover=False):
        if (
            not isinstance(client_id, str)
            or not re.fullmatch(r"[A-Za-z0-9]{1,128}", client_id)
            or not isinstance(client_secret, str)
            or not 1 <= len(client_secret) <= 1024
            or any(not 33 <= ord(char) <= 126 for char in client_secret)
        ):
            raise IgdbClientError("IGDB_CREDENTIALS_INVALID")
        self._include_cover = include_cover is True
        self._client_id = client_id
        self._client_secret = client_secret
        self._opener = (opener if opener is not None
                        else build_opener(ProxyHandler({}), _NoRedirect()))
        self._clock = monotonic
        self._wall_clock = wall_clock
        self._sleep = sleep
        self._lock = Lock()
        self._next_request = None
        self._token = None
        self._expires_at = 0.0
        self._validated_at = None
        self._queries = 0
        self._issues = 0
        self._requests = 0
        self._retried = False
        self._failed = False

    def _clear_token(self):
        self._token = None
        self._expires_at = 0.0
        self._validated_at = None

    def _request(self, request, maximum):
        if self._requests >= MAX_REQUESTS:
            raise IgdbClientError("IGDB_REQUEST_BUDGET")
        self._requests += 1
        now = self._clock()
        if self._next_request is not None and now < self._next_request:
            self._sleep(self._next_request - now)
        self._next_request = self._clock() + MIN_INTERVAL
        try:
            with self._opener.open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise IgdbClientError("IGDB_UNEXPECTED_STATUS")
                data = response.read(maximum + 1)
        except HTTPError as exc:
            try:
                if exc.code == 429 or (exc.headers or {}).get("Retry-After"):
                    raise RateLimited(retry_deadline(
                        exc.headers or {}, self._wall_clock(),
                    )) from None
                if exc.code == 401:
                    raise _Unauthorized("IGDB_UNAUTHORIZED") from None
                raise IgdbClientError(f"IGDB_HTTP_{exc.code}") from None
            finally:
                exc.close()
        except (URLError, OSError, HTTPException):
            raise IgdbClientError("IGDB_NETWORK_ERROR") from None
        if len(data) > maximum:
            raise IgdbClientError("IGDB_RESPONSE_SIZE_LIMIT")
        try:
            return json.loads(data, object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise IgdbClientError("IGDB_INVALID_JSON") from None

    def _issue(self):
        if self._issues >= MAX_ISSUES:
            raise IgdbClientError("IGDB_TOKEN_ISSUE_BUDGET")
        self._issues += 1
        self._clear_token()
        request = Request(TOKEN_URL, method="POST", data=urlencode({
            "client_id": self._client_id, "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }).encode("ascii"), headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        started = self._clock()
        try:
            data = self._request(request, AUTH_MAX_BYTES)
        except _Unauthorized:
            raise IgdbClientError("IGDB_TOKEN_ISSUE_REJECTED") from None
        if type(data) is not dict:
            raise IgdbClientError("IGDB_TOKEN_RESPONSE_INVALID")
        token, kind = data.get("access_token"), data.get("token_type")
        if (
            not isinstance(token, str) or not 1 <= len(token) <= 2048
            or not TOKEN_PATTERN.fullmatch(token)
            or not isinstance(kind, str) or kind.lower() != "bearer"
        ):
            raise IgdbClientError("IGDB_TOKEN_RESPONSE_INVALID")
        self._expires_at = started + _ttl(data.get("expires_in"))
        self._token = token

    def _validate_token(self):
        request = Request(VALIDATE_URL, method="GET", headers={
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        })
        started = self._clock()
        data = self._request(request, AUTH_MAX_BYTES)
        if (
            type(data) is not dict or data.get("client_id") != self._client_id
            or data.get("login") is not None or data.get("user_id") is not None
            or data.get("scopes") not in (None, [])
        ):
            raise IgdbClientError("IGDB_TOKEN_IDENTITY_MISMATCH")
        self._expires_at = min(self._expires_at, started + _ttl(data.get("expires_in")))
        self._validated_at = started

    def _ensure_token(self):
        now = self._clock()
        if self._token is None or now + EXPIRY_MARGIN >= self._expires_at:
            self._issue()
        if (self._validated_at is None
                or now - self._validated_at >= VALIDATION_INTERVAL):
            self._validate_token()
        if self._clock() + EXPIRY_MARGIN >= self._expires_at:
            raise IgdbClientError("IGDB_TOKEN_EXPIRY_INVALID")

    def _query_once(self, endpoint, body):
        self._ensure_token()
        request = Request(API_BASE + endpoint, method="POST", data=body.encode(),
                          headers={
                              "Client-ID": self._client_id,
                              "Authorization": f"Bearer {self._token}",
                              "Content-Type": "text/plain; charset=utf-8",
                              "Accept": "application/json",
                          })
        data = self._request(request, MAX_BYTES)
        if type(data) is not list or any(type(row) is not dict for row in data):
            raise IgdbClientError("IGDB_RESPONSE_INVALID")
        return data

    def query(self, endpoint, body):
        """Adapter Query implementation; no retries except one rejected token."""
        _validate_query(endpoint, body, include_cover=self._include_cover)
        with self._lock:
            if self._failed:
                raise IgdbClientError("IGDB_CYCLE_BLOCKED")
            if self._queries >= MAX_QUERIES:
                raise IgdbClientError("IGDB_QUERY_BUDGET")
            self._queries += 1
            try:
                try:
                    return self._query_once(endpoint, body)
                except _Unauthorized:
                    if self._retried:
                        raise IgdbClientError("IGDB_UNAUTHORIZED") from None
                    self._retried = True
                    self._clear_token()
                    try:
                        return self._query_once(endpoint, body)
                    except _Unauthorized:
                        raise IgdbClientError("IGDB_UNAUTHORIZED") from None
            except CollectionError:
                self._clear_token()
                self._failed = True
                raise
