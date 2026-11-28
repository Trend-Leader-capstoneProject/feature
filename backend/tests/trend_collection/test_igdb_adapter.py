"""Deterministic IGDB review tests; no credentials, HTTP or database."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.trend_collection.igdb_adapter import (
    DIVERSITY_SCOPE,
    IGDB_ID,
    VISITS_ID,
    IgdbBlocked,
    IgdbReviewAdapter,
    parse_popularity,
    validate_metric,
)

NOW = datetime(2026, 11, 20, 6, tzinfo=timezone.utc)
STAMP = int((NOW - timedelta(hours=6)).timestamp())
METRIC = [{"id": VISITS_ID, "name": "Visits",
           "external_popularity_source": {"id": IGDB_ID, "name": "IGDB"}}]


def popularity(game_id=1, value=0.01, stamp=STAMP):
    return {"game_id": game_id, "value": value, "calculated_at": stamp,
            "popularity_type": VISITS_ID, "external_popularity_source": IGDB_ID}


def game(game_id=1, *, mobile=False):
    platforms = ([{"id": 34, "name": "Android"}, {"id": 39, "name": "iOS"}]
                 if mobile else [{"id": 6, "name": "PC (Microsoft Windows)"}])
    return {
        "id": game_id, "name": f"Fixture Game {game_id}",
        "url": f"https://www.igdb.com/games/fixture-{game_id}",
        "game_type": {"type": "Main Game"},
        "platforms": platforms, "themes": [{"id": 1, "name": "Action"}],
        "age_ratings": [
            {"organization": {"id": 5, "name": "GRAC"},
             "rating_category": {"id": 24, "rating": "12+"}},
            {"organization": {"id": 1, "name": "ESRB"},
             "rating_category": {"id": 5, "rating": "T"}},
        ],
    }


def adapter(rows=None, games=None, *, diversity=False):
    rows = [popularity()] if rows is None else rows
    games = [game()] if games is None else games
    calls = []

    def query(endpoint, body):
        calls.append((endpoint, body))
        assert len(calls) <= 3
        if endpoint == "popularity_types":
            return deepcopy(METRIC)
        if endpoint == "popularity_primitives":
            return deepcopy(rows)
        if endpoint == "games":
            ids = body.split("where id = (")[1].split(")")[0].split(",")
            return deepcopy([row for row in games if str(row["id"]) in ids])
        raise AssertionError("unexpected endpoint")

    return IgdbReviewAdapter(query, diversity=diversity), calls


def test_collect_and_independent_verify_are_review_only():
    collect, calls = adapter()
    preview = collect.collect_review(NOW)
    assert preview["candidate_identity"] == "igdb-game:1"
    assert preview["publish_authorization"] == "NONE"
    assert preview["publication_status"] == "NOT_FOR_PUBLICATION"
    assert preview["ai_api_calls"] == 0
    assert preview["proposed_category_ref"] == {
        "parent_code": "GAME", "child_name": "PC 게임",
    }
    assert "source_published_at" not in preview
    assert "value" not in preview
    assert len(calls) == 3
    verify, calls = adapter()
    assert verify.verify_review(preview, NOW) == preview
    assert len(calls) == 3


def test_cursor_rotates_eligible_candidates_without_reranking():
    rows = [popularity(1, 3), popularity(2, 2), popularity(3, 1)]
    bad = game(1)
    bad.pop("age_ratings")
    games = [bad, game(2, mobile=True), game(3)]
    first, _ = adapter(rows, games)
    preview = first.collect_review(NOW)
    assert preview["rank"] == 2
    assert preview["proposed_category_ref"]["child_name"] == "모바일 게임"
    second, _ = adapter(rows, games)
    assert second.collect_review(NOW, after_game_id=2)["rank"] == 3
    wrap, _ = adapter(rows, games)
    assert wrap.collect_review(NOW, after_game_id=3)["rank"] == 2
    missing, _ = adapter(rows, games)
    assert missing.collect_review(NOW, after_game_id=99)["rank"] == 2


@pytest.mark.parametrize("changes", [
    {"age_ratings": []},
    {"age_ratings": [{"organization": {"id": 5, "name": "GRAC"},
                      "rating_category": {"id": 26, "rating": "19+"}}]},
    {"themes": [{"id": 42, "name": "Erotic"}]},
    {"themes": []},
    {"themes": [{"id": 1000, "name": "Unknown"}]},
    {"platforms": [{"id": 34, "name": "Android"},
                   {"id": 6, "name": "PC (Microsoft Windows)"}]},
    {"platforms": [{"id": 82, "name": "Web browser"}]},
    {"platforms": [{"id": 6, "name": "Android"}]},
    {"game_type": {"type": "Expansion"}},
    {"url": "https://www.igdb.com/games/test?next=example"},
    {"url": "https://www.igdb.com.evil.example/games/test"},
    {"name": "Bad\x00title"},
    {"name": "X" * 256},
])
def test_ineligible_game_is_not_selected(changes):
    client, _ = adapter(games=[{**game(), **changes}])
    assert client.collect_review(NOW) is None


def test_other_organization_adult_rating_blocks_even_with_grac():
    row = game()
    row["age_ratings"].append({
        "organization": {"id": 2, "name": "PEGI"},
        "rating_category": {"id": 12, "rating": "18"},
    })
    client, _ = adapter(games=[row])
    assert client.collect_review(NOW) is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, -1, 0, "1"])
def test_invalid_popularity_value(value):
    with pytest.raises(IgdbBlocked):
        parse_popularity([popularity(value=value)], NOW)


@pytest.mark.parametrize("rows", [
    [popularity(1, 2), popularity(1, 1)],
    [popularity(1, 1), popularity(2, 2)],
    [popularity(1, 2), popularity(2, 1, STAMP + 1)],
    [{**popularity(), "external_popularity_source": 14}],
    [{**popularity(), "popularity_type": True}],
    [{**popularity(), "game_id": True}],
])
def test_invalid_source_identity_order_or_timestamp(rows):
    with pytest.raises(IgdbBlocked):
        parse_popularity(rows, NOW)


def test_freshness_exact_48h_and_future():
    edge = int((NOW - timedelta(hours=48)).timestamp())
    assert parse_popularity([popularity(stamp=edge)], NOW)
    for stamp in (edge - 1, int(NOW.timestamp()) + 1):
        with pytest.raises(IgdbBlocked):
            parse_popularity([popularity(stamp=stamp)], NOW)


def test_tied_candidates_are_not_selected():
    client, _ = adapter([popularity(1), popularity(2)], [game(1), game(2)])
    assert client.collect_review(NOW) is None


@pytest.mark.parametrize("field,value", [
    ("rank", True), ("title", "forged"), ("game_id", 2),
    ("publish_authorization", "ALLOWED"), ("evidence_digest", "0" * 64),
    ("calculated_at", NOW.isoformat()),
])
def test_independent_verification_rejects_preview_tampering(field, value):
    collect, _ = adapter()
    preview = collect.collect_review(NOW)
    verify, _ = adapter()
    with pytest.raises(IgdbBlocked):
        verify.verify_review({**preview, field: value}, NOW)


def test_independent_verification_rejects_changed_source_and_stale_preview():
    collect, _ = adapter()
    preview = collect.collect_review(NOW)
    verify, _ = adapter(games=[{**game(), "name": "Changed"}])
    with pytest.raises(IgdbBlocked):
        verify.verify_review(preview, NOW)
    stale, calls = adapter()
    with pytest.raises(IgdbBlocked):
        stale.verify_review(preview, NOW + timedelta(minutes=10, seconds=1))
    assert calls == []


def test_empty_list_no_game_request():
    client, calls = adapter(rows=[])
    assert client.collect_review(NOW) is None
    assert len(calls) == 2


def test_wrong_metric_identity_rejected():
    with pytest.raises(IgdbBlocked):
        validate_metric([{**METRIC[0], "id": True}])


def test_missing_metadata_does_not_create_candidate():
    client, _ = adapter(games=[])
    assert client.collect_review(NOW) is None


def test_diversity_multiplatform_preserves_rating_and_independent_verification():
    multi = game()
    multi["platforms"].append({"id": 167, "name": "PlayStation 5"})
    collector, calls = adapter(games=[multi], diversity=True)
    preview = collector.collect_review(NOW)
    assert preview["scope"] == DIVERSITY_SCOPE
    assert preview["proposed_category_ref"]["child_name"] == "기타"
    assert collector.diagnostics == {"examined": 1, "eligible": 1, "ROOT_OTHER": 1}
    assert len(calls) == 3
    writer, calls = adapter(games=[multi], diversity=True)
    assert writer.verify_review(preview, NOW) == preview
    assert len(calls) == 3
    legacy, _ = adapter(games=[multi])
    assert legacy.collect_review(NOW) is None
    multi["age_ratings"][0]["rating_category"] = {"id": 26, "rating": "19+"}
    blocked, _ = adapter(games=[multi], diversity=True)
    assert blocked.collect_review(NOW) is None
    assert blocked.diagnostics["ADULT_RATING"] == 1
