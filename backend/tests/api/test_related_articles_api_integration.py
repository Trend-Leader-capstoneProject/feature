"""Related article read contract through both real list endpoints."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.dependencies.auth_dependency import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
    UserStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_related_article import TrendRelatedArticle
from app.models.trend_source import TrendSource
from app.models.user import User
from app.models.user_interest_category import UserInterestCategory
from app.repositories.trend_repository import TrendRepository
from app.trend_collection.searchapi_interest import SOURCE_URL

pytestmark = pytest.mark.integration


def _trend(session: Session, *, collected: datetime, source="interest",
           status=TrendStatus.ACTIVE) -> Trend:
    key = uuid4().hex
    trend = Trend(
        title=f"Reference fixture {key}", normalized_title=key, status=status,
        first_collected_at=collected, last_collected_at=collected,
    )
    session.add(trend)
    session.flush()
    if source != "none":
        identity = "searchapi-interest:" + sha256(key.encode()).hexdigest()
        session.add(TrendSource(
            trend_id=trend.trend_id, platform=TrendSourcePlatform.ETC,
            external_id=identity if source == "interest" else None,
            source_key=sha256(identity.encode()).hexdigest(),
            source_url=SOURCE_URL if source == "interest" else "https://example.com",
            collected_at=collected,
        ))
    return trend


def _article(session: Session, trend: Trend, *, order: int, published: datetime,
             collected: datetime | None = None) -> TrendRelatedArticle:
    url = f"https://example.com/article/{trend.normalized_title}-{order}"
    row = TrendRelatedArticle(
        trend_id=trend.trend_id, article_url=url,
        url_key=sha256(url.encode()).hexdigest(), publisher=f"Fixture {order}",
        title=None, published_at=published,
        collected_at=collected or trend.last_collected_at, selection_order=order,
    )
    session.add(row)
    return row


def test_article_batch_visibility_boundaries(db_session: Session):
    now = datetime.now(UTC).replace(microsecond=0)
    at = now.replace(tzinfo=None)
    observed = at - timedelta(hours=1)
    visible = _trend(db_session, collected=observed)
    fresh = _article(
        db_session, visible, order=2, published=at - timedelta(hours=47),
    )
    _article(db_session, visible, order=1, published=at - timedelta(hours=48))
    expired = _trend(db_session, collected=at - timedelta(hours=24))
    _article(db_session, expired, order=1, published=expired.last_collected_at)
    hidden = _trend(db_session, collected=observed, status=TrendStatus.HIDDEN)
    _article(db_session, hidden, order=1, published=observed)
    other = _trend(db_session, collected=observed, source="other")
    _article(db_session, other, order=1, published=observed)
    missing = _trend(db_session, collected=observed, source="none")
    _article(db_session, missing, order=1, published=observed)
    mismatch = _trend(db_session, collected=observed)
    _article(db_session, mismatch, order=1, published=observed,
             collected=observed + timedelta(seconds=1))
    future = _trend(db_session, collected=at + timedelta(seconds=1))
    _article(db_session, future, order=1, published=at)
    db_session.flush()

    repo = TrendRepository(db_session, utc_now=lambda: now)
    ids = [t.trend_id for t in (
        visible, expired, hidden, other, missing, mismatch, future,
    )]
    statements = []

    def record(*args):
        statements.append(args[2])

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        assert repo.find_related_articles_by_trend_ids([]) == {}
        assert statements == []
        assert repo.find_related_articles_by_trend_ids(ids) == {
            visible.trend_id: [fresh],
        }
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert len(statements) == 1


@pytest.mark.parametrize("personalized", [False, True])
def test_list_endpoints_return_ordered_references_and_empty_fallback(
    db_session: Session, personalized: bool,
):
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    observed = now - timedelta(minutes=5)
    root = Category(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="Related articles API fixture",
        sort_order=1, is_active=True, parent_id=None,
    )
    user = User(name="Related articles API fixture", status=UserStatus.ACTIVE)
    db_session.add_all([root, user])
    db_session.flush()
    child = Category(
        category_code=None, category_name="Related article child",
        sort_order=1, is_active=True, parent_id=root.category_id,
    )
    db_session.add(child)
    db_session.flush()
    db_session.add(UserInterestCategory(
        user_id=user.user_id, category_id=root.category_id,
    ))
    with_articles = _trend(db_session, collected=observed)
    without_articles = _trend(db_session, collected=observed)
    non_interest = _trend(db_session, collected=observed, source="other")
    for trend in (with_articles, without_articles, non_interest):
        db_session.add(TrendCategoryMap(
            trend_id=trend.trend_id, category_id=child.category_id, is_primary=True,
        ))
    second = _article(db_session, with_articles, order=2, published=observed)
    first = _article(db_session, with_articles, order=1, published=observed)
    _article(db_session, non_interest, order=1, published=observed)
    db_session.flush()

    application = create_app()

    def override_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_current_user] = lambda: user
    path = "/api/trends/personalized" if personalized else "/api/trends"
    params = {} if personalized else {"category_id": child.category_id}
    selects = []

    def record(*args):
        sql = " ".join(args[2].lower().split())
        if sql.startswith("select") and "from trend_related_articles" in sql:
            selects.append(sql)

    connection = db_session.connection()
    try:
        with TestClient(application) as client:
            event.listen(connection, "before_cursor_execute", record)
            try:
                response = client.get(path, params=params)
            finally:
                event.remove(connection, "before_cursor_execute", record)
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    cards = {row["trend_id"]: row for row in response.json()["data"]["items"]}
    assert cards[with_articles.trend_id]["latest_source"]["source_url"] == SOURCE_URL
    assert cards[with_articles.trend_id]["related_articles"] == [
        {"publisher": item.publisher, "title": None, "url": item.article_url,
         "published_at": observed.isoformat() + "Z"}
        for item in (first, second)
    ]
    assert cards[without_articles.trend_id]["related_articles"] == []
    assert cards[non_interest.trend_id]["related_articles"] == []
    assert len(selects) == 1
