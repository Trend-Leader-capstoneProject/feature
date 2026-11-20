"""Transport and token lifecycle tests, no live requests or credentials."""

import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest

from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.igdb_adapter import (
    GAME_FIELDS,
    POPULARITY_QUERY,
    TYPE_QUERY,
)
from app.trend_collection.igdb_client import (
    API_BASE,
    AUTH_MAX_BYTES,
    TOKEN_URL,
    VALIDATE_URL,
    IgdbClient,
    IgdbClientError,
    _NoRedirect,
)

CLIENT_ID = "fixtureclient"
SECRET = "fixture-secret+&"
TOKEN = "fixture-token"


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, clock, replies):
        self.clock = clock
        self.replies = iter(replies)
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout, self.clock()))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        return Response(data)


def issued(token=TOKEN, expires=7200):
    return {"access_token": token, "token_type": "bearer", "expires_in": expires}


def validated(expires=7200):
    return {"client_id": CLIENT_ID, "scopes": [], "expires_in": expires,
            "login": None, "user_id": None}


def error(code, headers=None):
    return HTTPError(API_BASE, code, SECRET, headers or {}, io.BytesIO(b"secret"))


def client(replies):
    clock = Clock()
    opener = Opener(clock, replies)
    instance = IgdbClient(CLIENT_ID, SECRET, opener=opener, monotonic=clock,
                          wall_clock=lambda: 1000, sleep=clock.sleep)
    return instance, opener, clock


def urls(opener):
    return [request.full_url for request, _, _ in opener.calls]


def test_token_is_validated_and_reused_for_three_sequential_queries():
    instance, opener, _ = client([issued(), validated(), [], [], []])
    instance.query("popularity_types", TYPE_QUERY)
    instance.query("popularity_primitives", POPULARITY_QUERY)
    body = f"fields {GAME_FIELDS}; where id = (1,2); limit 2;"
    instance.query("games", body)
    assert urls(opener) == [TOKEN_URL, VALIDATE_URL, API_BASE + "popularity_types",
                            API_BASE + "popularity_primitives", API_BASE + "games"]
    issue, validate, *queries = [call[0] for call in opener.calls]
    assert issue.get_method() == "POST" and "?" not in issue.full_url
    assert parse_qs(issue.data.decode()) == {
        "client_id": [CLIENT_ID], "client_secret": [SECRET],
        "grant_type": ["client_credentials"],
    }
    assert validate.get_method() == "GET" and validate.data is None
    assert validate.get_header("Authorization") == f"Bearer {TOKEN}"
    for request in queries:
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        assert request.get_header("Client-id") == CLIENT_ID
        assert SECRET not in request.full_url and SECRET not in request.data.decode()
    times = [call[2] for call in opener.calls]
    assert all(b - a >= 0.5 for a, b in zip(times, times[1:]))
    with pytest.raises(IgdbClientError, match="IGDB_QUERY_BUDGET"):
        instance.query("popularity_types", TYPE_QUERY)
    assert len(opener.calls) == 5


@pytest.mark.parametrize("endpoint,body", [
    ("https://evil.example", TYPE_QUERY), ("games", "fields *;"),
    ("popularity_types", "fields *;"),
    ("games", f"fields {GAME_FIELDS}; where id = (1,1); limit 2;"),
    ("games", f"fields {GAME_FIELDS}; where id = (1); limit 2;"),
    ("games", f"fields {GAME_FIELDS}; where id = (0); limit 1;"),
    ("games", f"fields {GAME_FIELDS}; where id = (1); limit 1; fields *;"),
])
def test_query_allowlist_blocks_before_authentication(endpoint, body):
    instance, opener, _ = client([])
    with pytest.raises(IgdbClientError, match="IGDB_QUERY_NOT_ALLOWED"):
        instance.query(endpoint, body)
    assert not opener.calls


def test_expiry_reissues_and_hourly_validation_is_enforced():
    instance, opener, clock = client([
        issued(expires=4000), validated(4000), [], validated(300), [],
        issued("fresh-token"), validated(), [],
    ])
    instance.query("popularity_types", TYPE_QUERY)
    clock.now = 3601
    instance.query("popularity_primitives", POPULARITY_QUERY)
    clock.now = 3950
    instance.query("popularity_types", TYPE_QUERY)
    assert urls(opener).count(TOKEN_URL) == 2
    assert urls(opener).count(VALIDATE_URL) == 3
    assert opener.calls[-1][0].get_header("Authorization") == "Bearer fresh-token"


def test_one_401_refresh_then_retry_and_second_401_blocks_cycle():
    instance, opener, _ = client([
        issued(), validated(), error(401), issued("fresh-token"), validated(), [],
        error(401),
    ])
    instance.query("popularity_types", TYPE_QUERY)
    with pytest.raises(IgdbClientError, match="IGDB_UNAUTHORIZED"):
        instance.query("popularity_primitives", POPULARITY_QUERY)
    with pytest.raises(IgdbClientError, match="IGDB_CYCLE_BLOCKED"):
        instance.query("popularity_primitives", POPULARITY_QUERY)
    assert urls(opener).count(TOKEN_URL) == 2
    assert len(opener.calls) == 7


def test_rejected_client_credentials_do_not_retry():
    instance, opener, _ = client([error(401)])
    with pytest.raises(IgdbClientError, match="IGDB_TOKEN_ISSUE_REJECTED"):
        instance.query("popularity_types", TYPE_QUERY)
    assert urls(opener) == [TOKEN_URL]


@pytest.mark.parametrize("headers,deadline", [
    ({"Retry-After": "120"}, 1120), ({"Retry-After": "invalid"}, None), ({}, 1060),
])
def test_rate_limit_preserves_deadline_and_blocks_more_requests(headers, deadline):
    instance, opener, _ = client([issued(), validated(), error(429, headers)])
    with pytest.raises(RateLimited) as exc:
        instance.query("popularity_types", TYPE_QUERY)
    assert exc.value.retry_not_before == deadline
    with pytest.raises(IgdbClientError, match="IGDB_CYCLE_BLOCKED"):
        instance.query("popularity_types", TYPE_QUERY)
    assert len(opener.calls) == 3


@pytest.mark.parametrize("reply", [
    {**issued(), "expires_in": True}, {**issued(), "expires_in": 1},
    {**issued(), "access_token": "invalid\r\nheader"},
    {**issued(), "token_type": "other"}, b"{", b"{\"a\":1,\"a\":2}",
    b'{"value":NaN}', b"x" * (AUTH_MAX_BYTES + 1),
])
def test_invalid_token_or_response_is_rejected_without_data_call(reply):
    instance, opener, _ = client([reply])
    with pytest.raises(IgdbClientError) as exc:
        instance.query("popularity_types", TYPE_QUERY)
    assert SECRET not in str(exc.value) and TOKEN not in str(exc.value)
    assert urls(opener) == [TOKEN_URL]


@pytest.mark.parametrize("reply", [
    {**validated(), "client_id": "other"}, {**validated(), "user_id": "1"},
    {**validated(), "scopes": ["user:read"]}, {**validated(), "expires_in": 0},
])
def test_token_identity_must_be_matching_unscoped_app(reply):
    instance, opener, _ = client([issued(), reply])
    with pytest.raises(IgdbClientError):
        instance.query("popularity_types", TYPE_QUERY)
    assert urls(opener) == [TOKEN_URL, VALIDATE_URL]


@pytest.mark.parametrize("failure", [
    URLError(SECRET), TimeoutError(SECRET), error(500),
])
def test_network_and_http_errors_are_bounded(failure):
    instance, opener, _ = client([issued(), validated(), failure])
    with pytest.raises(IgdbClientError) as exc:
        instance.query("popularity_types", TYPE_QUERY)
    assert SECRET not in str(exc.value)
    assert len(opener.calls) == 3


def test_redirect_handler_never_follows_redirect():
    handler = _NoRedirect()
    for status in (301, 302, 303, 307, 308):
        callback = getattr(handler, f"http_error_{status}")
        with pytest.raises(IgdbClientError, match="IGDB_REDIRECT_BLOCKED"):
            callback(None, io.BytesIO(), status, "redirect",
                     {"Location": "https://evil"})


def test_bad_data_shape_blocks_cycle():
    instance, opener, _ = client([issued(), validated(), {"message": SECRET}])
    with pytest.raises(IgdbClientError, match="IGDB_RESPONSE_INVALID"):
        instance.query("popularity_types", TYPE_QUERY)
    assert len(opener.calls) == 3


def test_validation_401_refreshes_once_and_respects_request_budget():
    instance, opener, _ = client([
        issued(), error(401), issued("fresh-token"), validated(), [], [], [],
    ])
    for _ in range(3):
        instance.query("popularity_types", TYPE_QUERY)
    assert urls(opener).count(TOKEN_URL) == 2
    assert len(opener.calls) == 7


def test_total_request_budget_limits_repeated_validation():
    instance, opener, clock = client([
        issued(expires=20000), validated(20000), [],
        validated(12000), [], validated(12000), error(401), issued("fresh-token"),
    ])
    instance.query("popularity_types", TYPE_QUERY)
    clock.now = 3601
    instance.query("popularity_types", TYPE_QUERY)
    clock.now = 7202
    with pytest.raises(IgdbClientError, match="IGDB_REQUEST_BUDGET"):
        instance.query("popularity_types", TYPE_QUERY)
    assert len(opener.calls) == 8
