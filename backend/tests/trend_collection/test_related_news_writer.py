"""Related News scope, atomic Writer and scheduler contract (no live I/O)."""

import os
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trend import Trend
from app.models.trend_related_article import TrendRelatedArticle

from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.publication_policy import _digest
from app.trend_collection.searchapi_interest import SearchInterestAdapter
from app.trend_collection.searchapi_related_articles import ArticleLinkRule
from app.trend_collection.supply_adapter import (
    INTEREST_RELATED_SCOPE,
    INTEREST_SCOPE,
    INTEREST_SOURCE_ID,
    SupplyBlocked,
    bind_snapshot,
)
from scripts import run_auto_supply as supply
from scripts.ap3_writer_isolation import IsolationError
from scripts.ap3_writer_observation import TABLE_PRIVILEGES, check_table_grants
from scripts.auto_supply_control import INTERVAL, cycle, load_state, next_state

NOW = datetime(2026, 11, 26, 1, tzinfo=timezone.utc)
RULE = ArticleLinkRule("a.example.com", "/article/", "A", "fixture-rights")
TOPIC = "작품2"
TOPICS = {TOPIC: ("ENTERTAINMENT", "드라마")}
READY = {"pending": False, "not_before": 0, "rate_failures": 0}


def _raw(*, related=True):
    source = {
        "source_id": INTEREST_SOURCE_ID,
        "scope": INTEREST_RELATED_SCOPE if related else INTEREST_SCOPE,
        "rights": dict(supply.RIGHTS), "rights_ref": "fixture-observation",
    }
    if related:
        source["article_rules"] = [asdict(RULE)]
    return {
        "enabled": True, "profile_id": supply.PROFILE,
        "policy_version": supply.VERSION, "sources": [source],
        "environment": "local", "collector_uid": 101, "writer_uid": 102,
        "port": 3309, "database": "trend_leader",
        "current_user": "trend_auto_writer@host",
        "journal_id": "a" * 32, "journal_device": 1, "journal_inode": 2,
        "approved_at": (NOW - timedelta(days=1)).isoformat(),
        "valid_until": (NOW + timedelta(days=1)).isoformat(),
        "approved_by": "fixture-operator",
        "g5_ref": "fixture-g5-ref", "g6_ref": "fixture-g6-ref",
    }


def _profile(*, related=True):
    return supply.parse_profile(_raw(related=related), NOW)


def _client(token):
    client = Mock()
    item = {
        "query": TOPIC, "is_active": True,
        "start_date": (NOW - timedelta(hours=1)).isoformat(),
        "categories": ["entertainment"],
    }
    if token is not None:
        item["news_token"] = token
    client.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now", "geo": "KR",
            "time": "past_24_hours",
        },
        "trends": [item],
    }
    client.related_news.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now_news", "news_token": token,
        },
        "news": [{
            "title": "작품2 소식", "link": "https://a.example.com/article/1",
            "source": "A", "iso_date": (NOW - timedelta(hours=2)).isoformat(),
        }],
    }
    return client


def _adapter(client):
    return SearchInterestAdapter(
        client, topics=TOPICS, clock=lambda: NOW, allow_missing_news_token=True,
    )


def _preview():
    return _adapter(_client("collector-token")).collect_preview()


def _snapshot():
    snap, _ = _adapter(_client("writer-token")).verify_with_news(
        _preview(), NOW, rules=(RULE,),
    )
    return bind_snapshot(snap, policy=supply.VERSION, target=_profile().target)


def test_profile_requires_separate_scope_and_protected_rules():
    assert not _profile(related=False).related_articles_enabled
    assert _profile().related_articles_enabled
    assert _profile().source(INTEREST_SOURCE_ID).article_rules == (RULE,)
    raw = _raw(related=False)
    raw["sources"][0]["article_rules"] = [asdict(RULE)]
    with pytest.raises(SupplyBlocked):
        supply.parse_profile(raw, NOW)
    raw = _raw()
    del raw["sources"][0]["article_rules"]
    with pytest.raises(SupplyBlocked):
        supply.parse_profile(raw, NOW)


@pytest.mark.parametrize("change", [
    {"host": "127.0.0.1"}, {"evidence_ref": "PASS"}, {"allow_title": "true"},
])
def test_invalid_protected_rules_rejected(change):
    raw = _raw()
    raw["sources"][0]["article_rules"] = [{**asdict(RULE), **change}]
    with pytest.raises(SupplyBlocked, match="ARTICLE_RULES_INVALID"):
        supply.parse_profile(raw, NOW)


def test_writer_uses_only_independent_token_and_preserves_legacy_digest():
    writer = _client("writer-token")
    preview = _preview()
    assert "collector-token" not in str(preview)
    old = _adapter(writer).verify(preview, NOW)
    writer.related_news.assert_not_called()
    payload = asdict(old)
    payload.pop("related_articles")
    assert old.content_digest == _digest(payload)
    writer.trending_now.reset_mock()
    new, result = _adapter(writer).verify_with_news(preview, NOW, rules=(RULE,))
    writer.trending_now.assert_called_once()
    writer.related_news.assert_called_once_with("writer-token")
    assert result.status == "AVAILABLE"
    assert new.candidate_identity == old.candidate_identity
    assert new.content_digest != old.content_digest
    assert len(new.related_articles) == 1
    assert new.related_articles[0].title is None
    assert "writer-token" not in str(asdict(new))


def test_missing_token_still_allows_observation_in_new_scope():
    collector, writer = _client(None), _client(None)
    preview = _adapter(collector).collect_preview()
    assert preview is not None
    snap, result = _adapter(writer).verify_with_news(preview, NOW, rules=(RULE,))
    assert snap.related_articles == ()
    assert result.status == "DISABLED"
    writer.related_news.assert_not_called()


def test_required_observation_failure_never_calls_news():
    writer = _client("writer-token")
    writer.trending_now.return_value["trends"][0]["is_active"] = False
    with pytest.raises(SupplyBlocked, match="INTEREST_OBSERVATION_UNCONFIRMED"):
        _adapter(writer).verify_with_news(_preview(), NOW, rules=(RULE,))
    writer.related_news.assert_not_called()


@pytest.mark.parametrize("change", [
    {"selection_order": 2}, {"url_key": "0" * 64}, {"title": "작품2 소식"},
    {"published_at_utc": (NOW + timedelta(seconds=1)).isoformat()},
    {"url": "https://evil.example/article/1"},
])
def test_writer_rechecks_article_snapshot(change):
    snap = _snapshot()
    validate_snapshot_freshness(_profile(), snap, NOW)
    with pytest.raises(SupplyBlocked, match="ARTICLE_SCOPE_NOT_APPROVED"):
        validate_snapshot_freshness(_profile(related=False), snap, NOW)
    bad = replace(snap, related_articles=(replace(snap.related_articles[0],
                                                   **change),))
    with pytest.raises(SupplyBlocked, match="ARTICLE_SNAPSHOT_INVALID"):
        validate_snapshot_freshness(_profile(), bad, NOW)


@pytest.mark.parametrize("related", [False, True])
def test_operational_writer_selects_scope(monkeypatch, related):
    profile, writer = _profile(related=related), _client("writer-token")
    monkeypatch.setattr(supply, "_operational_adapter",
                        lambda *_: _adapter(writer))
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    monkeypatch.setattr(supply, "OperationalJournal", Mock())
    write = Mock(return_value="COMMITTED")
    monkeypatch.setattr(supply, "_write", write)
    outcome = supply.run_writer(profile, {
        "source_id": INTEREST_SOURCE_ID, "preview": _preview(),
    })
    assert outcome["status"] == "COMMITTED"
    bound = write.call_args.args[1]
    assert bound.target == profile.target
    assert bool(bound.related_articles) is related
    assert writer.related_news.call_count == int(related)
    assert ("related_news_status" in outcome) is related


def test_optional_rate_limit_does_not_block_verified_observation(monkeypatch):
    writer = _client("writer-token")
    writer.related_news.side_effect = RateLimited(200000)
    monkeypatch.setattr(supply, "_operational_adapter",
                        lambda *_: _adapter(writer))
    monkeypatch.setattr(supply, "now_utc", lambda: NOW)
    monkeypatch.setattr(supply, "OperationalJournal", Mock())
    write = Mock(return_value="COMMITTED")
    monkeypatch.setattr(supply, "_write", write)
    result = supply.run_writer(_profile(), {
        "source_id": INTEREST_SOURCE_ID, "preview": _preview(),
    })
    assert result["status"] == "COMMITTED"
    assert result["related_news_status"] == "RATE_LIMITED"
    assert result["retry_not_before"] == 200000
    assert write.call_args.args[1].related_articles == ()


@pytest.mark.parametrize("mode", ["commit", "duplicate", "rollback", "unknown"])
def test_related_dml_journal_order_and_failure(monkeypatch, mode):
    snap, profile = _snapshot(), _profile()
    engine, journal = MagicMock(), Mock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.exec_driver_sql.return_value.scalar_one.return_value = 1
    events = []
    monkeypatch.setattr(supply, "_assert_current",
                        lambda p, s: validate_snapshot_freshness(p, s, NOW))
    monkeypatch.setattr(supply, "_make_engine", lambda _: engine)
    monkeypatch.setattr(supply, "_verify_session", Mock())
    monkeypatch.setattr(supply, "_category_id", Mock(return_value=2))
    monkeypatch.setattr(supply, "inspect_snapshot", Mock(
        return_value="SKIP_EXISTING_RELEASE" if mode == "duplicate" else "NEW",
    ))
    journal.claim.side_effect = lambda *_: events.append("STARTED")

    def parent(*_, **__):
        events.append("PARENT")
        return 42

    def article(statement, params):
        assert "INSERT INTO trend_related_articles" in str(statement)
        assert params["id"] == 42 and params["title"] is None
        assert params["slot"] == 1 and params["collected"].tzinfo is None
        events.append("ARTICLE")
        if mode == "rollback":
            raise RuntimeError("fixture failure")

    def commit():
        events.append("COMMIT")
        if mode == "unknown":
            raise RuntimeError("lost response")

    monkeypatch.setattr(supply, "insert_trend_item", parent)
    conn.execute.side_effect = article
    conn.commit.side_effect = commit
    journal.finish.side_effect = lambda *args: events.append(args[-1])
    result = supply._write(profile, snap, journal)
    if mode == "duplicate":
        assert result == "SKIP_EXISTING_RELEASE"
        assert events == []
    elif mode == "rollback":
        assert result == "HOLD"
        assert events == ["STARTED", "PARENT", "ARTICLE", "ROLLED_BACK"]
        conn.commit.assert_not_called()
    elif mode == "unknown":
        assert result == "HOLD"
        assert events == ["STARTED", "PARENT", "ARTICLE", "COMMIT",
                          "COMMIT_UNKNOWN"]
    else:
        assert result == "COMMITTED"
        assert events == ["STARTED", "PARENT", "ARTICLE", "COMMIT", "COMMITTED"]
    if mode != "duplicate":
        assert journal.claim.call_args.args[1] == snap.content_digest


def test_extra_grants_require_new_profile_and_no_broad_privileges():
    principal = "'trend_auto_writer'@'host'"
    database = "trend_leader"
    grants = [f"GRANT USAGE ON *.* TO {principal}"] + [
        f"GRANT {', '.join(sorted(privs))} ON `{database}`.`{table}` TO {principal}"
        for table, privs in TABLE_PRIVILEGES.items()
    ]
    check_table_grants(grants, database, "trend_auto_writer@host")
    new = (
        f"GRANT SELECT, INSERT ON `{database}`.`trend_related_articles` "
        f"TO {principal}"
    )
    with pytest.raises(IsolationError):
        check_table_grants(grants + [new], database, "trend_auto_writer@host")
    with pytest.raises(IsolationError):
        check_table_grants(grants, database, "trend_auto_writer@host",
                           related_articles=True)
    check_table_grants(grants + [new], database, "trend_auto_writer@host",
                       related_articles=True)
    with pytest.raises(IsolationError):
        check_table_grants(grants + [new.replace("INSERT", "UPDATE")],
                           database, "trend_auto_writer@host",
                           related_articles=True)


@pytest.mark.parametrize("status,deadline,pending", [
    ("COMMITTED", 180000, False),
    ("SKIP_EXISTING_RELEASE", None, True),
    ("HOLD", 180000, True),
])
def test_optional_rate_limit_keeps_terminal_rotation(status, deadline, pending):
    result = {"status": status, "related_news_status": "RATE_LIMITED",
              "retry_not_before": deadline}
    state = next_state(result, 100000, READY, writer=True,
                       source_id=INTEREST_SOURCE_ID)
    assert state["pending"] is pending
    assert state["not_before"] >= max(100000 + INTERVAL, deadline or 0)
    assert state.get("last_completed_source_id") == (
        None if status == "HOLD" else INTEREST_SOURCE_ID
    )
    assert state["related_news_rate_failures"] == 1


def test_optional_rate_streak_survives_other_source_success_and_resets_on_news():
    limited = {"status": "COMMITTED", "related_news_status": "RATE_LIMITED",
               "retry_not_before": 200000}
    first = next_state(limited, 100000, READY, writer=True,
                       source_id=INTEREST_SOURCE_ID)
    other = next_state({"status": "COMMITTED"}, 200001, first, writer=True,
                       source_id="igdb:visits")
    assert other["related_news_rate_failures"] == 1
    second = next_state(limited, 300000, other, writer=True,
                        source_id=INTEREST_SOURCE_ID)
    assert second["not_before"] >= 300000 + 2 * INTERVAL
    third = next_state(limited, 400000, second, writer=True,
                       source_id=INTEREST_SOURCE_ID)
    assert third["pending"] is True
    reset = next_state({"status": "COMMITTED", "related_news_status": "EMPTY"},
                       500000, second, writer=True, source_id=INTEREST_SOURCE_ID)
    assert "related_news_rate_failures" not in reset


@pytest.mark.skipif(os.name != "posix", reason="Linux durable scheduler")
def test_cycle_saves_completed_rate_limited_outcome(tmp_path):
    profile = _profile()
    envelope = {"source_id": INTEREST_SOURCE_ID, "preview": _preview()}
    outcome = {"status": "COMMITTED", "related_news_status": "RATE_LIMITED",
               "retry_not_before": 180000,
               "candidate_identity": "searchapi-interest:" + _preview()["case_key"]}
    child = Mock(side_effect=[(0, envelope), (0, outcome)])
    path = tmp_path / "scheduler.json"
    assert cycle(profile, path, READY, child=child, clock=lambda: 100000) == outcome
    import json

    saved = load_state(path, lambda p: json.loads(p.read_text()))
    assert saved["pending"] is False
    assert saved["not_before"] == 180000
    assert saved["related_news_rate_failures"] == 1
    assert child.call_count == 2


@pytest.mark.integration
def test_related_dml_stores_metadata_in_existing_transaction(db_session: Session):
    """Exercise the real article DML against the migrated, isolated MariaDB."""
    key = uuid4().hex
    parent = Trend(
        title=f"Related writer fixture {key}", normalized_title=key,
        first_collected_at=NOW.replace(tzinfo=None),
        last_collected_at=NOW.replace(tzinfo=None),
    )
    db_session.add(parent)
    db_session.flush()
    snapshot = _snapshot()
    with db_session.begin_nested():
        supply._insert_related_articles(
            db_session.connection(), parent.trend_id, snapshot,
        )
        row = db_session.scalars(
            select(TrendRelatedArticle).where(
                TrendRelatedArticle.trend_id == parent.trend_id,
            ),
        ).one()
        expected = snapshot.related_articles[0]
        assert row.article_url == expected.url
        assert row.url_key == expected.url_key
        assert row.publisher == expected.publisher
        assert row.title is None
        assert row.selection_order == 1
        assert row.published_at == (NOW - timedelta(hours=2)).replace(tzinfo=None)
        assert row.collected_at == NOW.replace(tzinfo=None)
