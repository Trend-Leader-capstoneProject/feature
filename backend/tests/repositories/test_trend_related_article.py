"""Schema and rollback-isolated MariaDB checks for optional article links."""

from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.trend import Trend
from app.models.trend_related_article import TrendRelatedArticle

NOW = datetime(2026, 11, 25, 5)


def test_related_article_metadata_contract():
    table = TrendRelatedArticle.__table__
    assert Base.metadata.tables["trend_related_articles"] is table
    assert list(table.primary_key.columns.keys()) == ["article_id"]
    assert set(table.columns.keys()) == {
        "article_id", "trend_id", "article_url", "url_key", "publisher",
        "title", "published_at", "collected_at", "selection_order",
    }
    assert {col.name for col in table.columns if col.nullable} == {"title"}
    fk, = table.foreign_keys
    assert fk.target_fullname == "trends.trend_id"
    assert fk.ondelete == "CASCADE"
    assert {tuple(c.columns.keys()) for c in table.constraints
            if isinstance(c, UniqueConstraint)} == {
        ("trend_id", "url_key"), ("trend_id", "selection_order"),
    }
    assert {c.name for c in table.constraints if isinstance(c, CheckConstraint)} == {
        "ck_trend_related_articles_selection_order",
        "ck_trend_related_articles_published_at",
    }
    assert Trend.related_articles.property.back_populates == "trend"
    assert table.dialect_options["mysql"]["engine"] == "InnoDB"


def _trend(session: Session) -> Trend:
    key = uuid4().hex
    trend = Trend(
        title=f"Related article test {key}", normalized_title=key,
        first_collected_at=NOW, last_collected_at=NOW,
    )
    session.add(trend)
    session.flush()
    return trend


def _values(trend_id: int, suffix: str, order: int) -> dict:
    url = f"https://example.com/article/{suffix}"
    return {
        "trend_id": trend_id, "article_url": url,
        "url_key": sha256(url.encode()).hexdigest(),
        "publisher": "Fixture publisher", "title": None,
        "published_at": NOW - timedelta(hours=1),
        "collected_at": NOW, "selection_order": order,
    }


@pytest.mark.integration
def test_related_article_slots_and_cascade(db_session: Session):
    """The test fixture applies Alembic to the approved test DB, never production."""
    parent = _trend(db_session)
    unrelated = _trend(db_session)
    parent_id = parent.trend_id
    other_id = unrelated.trend_id
    assert parent.related_articles == []
    db_session.add_all([
        TrendRelatedArticle(**_values(parent_id, "second", 2)),
        TrendRelatedArticle(**_values(parent_id, "first", 1)),
        TrendRelatedArticle(**_values(other_id, "first", 1)),
    ])
    db_session.flush()
    db_session.expire(parent, ["related_articles"])
    assert [item.selection_order for item in parent.related_articles] == [1, 2]
    assert all(item.title is None for item in parent.related_articles)

    # Core DELETE bypasses ORM cascades and exercises the migrated FK.
    db_session.execute(
        delete(Trend.__table__).where(Trend.trend_id == parent_id),
    )
    assert db_session.scalars(
        select(TrendRelatedArticle.article_id).where(
            TrendRelatedArticle.trend_id == parent_id,
        ),
    ).all() == []
    assert len(db_session.scalars(
        select(TrendRelatedArticle.article_id).where(
            TrendRelatedArticle.trend_id == other_id,
        ),
    ).all()) == 1


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["url", "slot", "third", "zero", "future", "fk"])
def test_related_article_constraints(db_session: Session, kind: str):
    parent = _trend(db_session)
    table = TrendRelatedArticle.__table__
    db_session.execute(insert(table), _values(parent.trend_id, "first", 1))
    candidate = _values(parent.trend_id, "second", 2)
    if kind == "url":
        candidate = _values(parent.trend_id, "first", 2)
    elif kind == "slot":
        candidate["selection_order"] = 1
    elif kind == "third":
        candidate["selection_order"] = 3
    elif kind == "zero":
        candidate["selection_order"] = 0
    elif kind == "future":
        candidate["published_at"] = NOW + timedelta(seconds=1)
    elif kind == "fk":
        candidate["trend_id"] = -1
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(insert(table), candidate)
    assert len(db_session.scalars(
        select(TrendRelatedArticle.article_id).where(
            TrendRelatedArticle.trend_id == parent.trend_id,
        ),
    ).all()) == 1
