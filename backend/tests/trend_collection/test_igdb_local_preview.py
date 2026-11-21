"""Ephemeral IGDB review card tests; no credentials, public API or DB."""

import http.client
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Thread
from types import SimpleNamespace

import pytest

from app.trend_collection.igdb_adapter import (
    IGDB_ID,
    VISITS_ID,
    IgdbBlocked,
    IgdbReviewAdapter,
)
from app.trend_collection.igdb_local_preview import (
    _card,
    build_local_review_html,
    serve_loopback,
)
from app.trend_collection.igdb_supply_snapshot import IgdbSnapshotBridge

NOW = datetime(2026, 11, 20, 7, tzinfo=timezone.utc)
STAMP = int((NOW - timedelta(hours=5)).timestamp())


def _game(*, name="Free Fire"):
    return {
        "id": 87622,
        "name": name,
        "url": "https://www.igdb.com/games/free-fire",
        "game_type": {"type": "Main Game"},
        "platforms": [{"id": 34, "name": "Android"}],
        "themes": [{"id": 1, "name": "Action"}],
        "age_ratings": [{
            "organization": {"id": 5, "name": "GRAC"},
            "rating_category": {"id": 25, "rating": "15+"},
        }],
    }


def _factory(*, empty=False, changed_second=False, name="Free Fire"):
    calls = []

    def new_client():
        index = len(calls)
        requests = []
        calls.append(requests)

        def query(endpoint, body):
            requests.append(endpoint)
            if endpoint == "popularity_types":
                return [{
                    "id": VISITS_ID, "name": "Visits",
                    "external_popularity_source": {
                        "id": IGDB_ID, "name": "IGDB",
                    },
                }]
            if endpoint == "popularity_primitives":
                return [] if empty else [{
                    "game_id": 87622,
                    "value": 0.12,
                    "popularity_type": VISITS_ID,
                    "external_popularity_source": IGDB_ID,
                    "calculated_at": STAMP,
                }]
            if endpoint == "games":
                return [_game(name="Changed" if changed_second and index else name)]
            raise AssertionError("UNEXPECTED_QUERY")

        return SimpleNamespace(query=query)

    return new_client, calls


def test_collection_to_independent_verification_to_transient_card():
    factory, calls = _factory()
    delays = []
    html = build_local_review_html(
        factory, clock=lambda: NOW, between_clients=delays.append,
    )
    assert len(calls) == 2
    assert calls == [
        ["popularity_types", "popularity_primitives", "games"],
        ["popularity_types", "popularity_primitives", "games"],
    ]
    assert delays == [0.5]
    assert "Free Fire" in html
    assert "IGDB Visits 관측 1위" in html
    assert "게임 · 모바일 게임" in html
    assert 'href="https://www.igdb.com/games/free-fire"' in html
    assert "미게시 · 독립 검증 완료" in html
    assert "최근 인기 검색 순위" not in html
    assert "<img" not in html and "<script" not in html


def test_no_candidate_does_not_create_writer_or_verification_client():
    factory, calls = _factory(empty=True)
    html = build_local_review_html(
        factory, clock=lambda: NOW, between_clients=lambda _: None,
    )
    assert len(calls) == 1
    assert calls[0] == ["popularity_types", "popularity_primitives"]
    assert "적격 후보가 없습니다" in html
    assert "DB 저장이나 Writer 실행은 없습니다" in html


def test_changed_source_in_independent_verification_never_renders():
    factory, calls = _factory(changed_second=True)
    with pytest.raises(IgdbBlocked, match="PREVIEW_MISMATCH"):
        build_local_review_html(
            factory, clock=lambda: NOW, between_clients=lambda _: None,
        )
    assert len(calls) == 2


def test_source_text_is_html_escaped_without_raw_script():
    malicious = '<script>alert("XSS")</script>'
    factory, _ = _factory(name=malicious)
    html = build_local_review_html(
        factory, clock=lambda: NOW, between_clients=lambda _: None,
    )
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert '&lt;script&gt;alert(&quot;XSS&quot;)' in html


def test_renderer_rejects_non_verified_object():
    with pytest.raises(ValueError, match="REVIEW_SNAPSHOT_INVALID"):
        _card({"title": "Forged"})



@pytest.mark.parametrize("unsafe_url", [
    "javascript:alert(1)",
    "https://www.igdb.com.evil.example/games/free-fire",
    "https://www.igdb.com/games/free-fire?redirect=evil",
])
def test_renderer_rechecks_official_source_url(unsafe_url):
    factory, _ = _factory()
    preview = IgdbReviewAdapter(factory().query).collect_review(NOW)
    snapshot = IgdbSnapshotBridge(factory().query).verify(preview, NOW)
    with pytest.raises(ValueError, match="REVIEW_SNAPSHOT_INVALID"):
        _card(replace(snapshot, source_url=unsafe_url))

def _http_request(port, *, path="/", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        headers = {"Host": host} if host is not None else {}
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_loopback_server_has_no_persistence_or_public_resource_path():
    generated = []

    def render():
        generated.append(1)
        return "<html>LOCAL</html>"

    with serve_loopback(render) as server:
        assert server.server_address[0] == "127.0.0.1"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, body = _http_request(server.server_port)
            assert status == 200 and body == b"<html>LOCAL</html>"
            assert headers["Cache-Control"].startswith("no-store")
            assert headers["Referrer-Policy"] == "no-referrer"
            assert headers["X-Frame-Options"] == "DENY"
            assert "default-src 'none'" in headers["Content-Security-Policy"]
            assert generated == [1]

            assert _http_request(server.server_port, path="/api/trends")[0] == 404
            assert _http_request(
                server.server_port, host="evil.example",
            )[0] == 400
            assert generated == [1]
        finally:
            server.shutdown()
            thread.join(timeout=3)


def test_error_page_never_leaks_upstream_exception():
    secret = "sensitive-client-secret"

    def fail():
        raise RuntimeError(secret)

    with serve_loopback(fail) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, body = _http_request(server.server_port)
            assert status == 503
            assert secret.encode() not in body
            assert headers["Cache-Control"].startswith("no-store")
        finally:
            server.shutdown()
            thread.join(timeout=3)


@pytest.mark.parametrize("port", [-1, 65536, True, None])
def test_only_valid_loopback_port_supported(port):
    with pytest.raises(ValueError, match="INVALID_PREVIEW_PORT"):
        serve_loopback(lambda: "", port=port)
