"""SearchApi reviewed Snapshot -> shared Writer DML -> actual API.

The approved case and upstream HTML are synthetic. All DML uses the existing
rollback-isolated test DB. No operational Writer, approval or live API calls.
"""

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app
from app.models.category import Category
from app.models.db_enums import CategoryCode
from app.repositories.trend_repository import TrendRepository
from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.searchapi_article_reader import ArticleReader
from app.trend_collection.searchapi_discovery import NewsLead, TrendingLead
from app.trend_collection.searchapi_evidence import (
    ArticleObservation,
    CrossSourceReview,
    ProposedFact,
    assess_cross_source_evidence,
    build_review_event_identity,
)
from app.trend_collection.searchapi_interest import (
    SCOPE as INTEREST_SCOPE,
    SOURCE_ID as INTEREST_SOURCE_ID,
    SOURCE_URL as INTEREST_URL,
    SearchInterestAdapter,
)
from app.trend_collection.searchapi_review_pipeline import SearchApiReviewCandidate
from app.trend_collection.searchapi_supply_snapshot import (
    SCOPE,
    SOURCE_ID,
    NewsSnapshot,
    ReviewedNewsCase,
    SearchApiSnapshotBridge,
)
from app.trend_collection.supply_adapter import ADAPTERS, SupplyBlocked, bind_snapshot
from scripts.ap3_writer_transaction import _category_id, insert_trend_item
from scripts.run_auto_supply import inspect_snapshot

pytestmark = pytest.mark.integration

ARTICLE_URL = "https://www.yna.co.kr/view/AKR20261123042700005"
EVENT_TITLE = "'굿데이' 시즌2, 2027년 상반기 공개 계획 발표"
EVENT_SUMMARY = (
    "제작사 TEO가 '굿데이' 시즌2의 2027년 상반기 공개 계획을 알렸습니다."
)
SECOND_URL = "https://mobile.newsis.com/view/NISX20261123_0003878761"
NOW = datetime(2026, 11, 23, 2, tzinfo=timezone.utc)
PUBLISHED = NOW - timedelta(hours=1)
BODY = (
    "제작사 TEO가 굿데이 시즌2의 2027년 상반기 공개 계획을 발표했다. "
    "이는 실제 기사를 복사하지 않고 만든 테스트용 가상 본문입니다. "
    "추가 일정과 출연진에 관한 내용은 이 사례의 검토 대상이 아닙니다."
)


class FakeArticleResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, body):
        self.url = url
        self.data = (
            '<meta property="article:published_time" '
            f'content="{PUBLISHED.isoformat()}"><article>{body}</article>'
        ).encode("utf-8")

    def read(self, limit):
        return self.data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def reviewed_bridge(*, changed_body=False):
    lead = TrendingLead(
        "지드래곤", PUBLISHED, "test-only-token",
        frozenset({"ENTERTAINMENT"}),
    )
    news = (
        NewsLead("테스트 기사 1", ARTICLE_URL, "YNA", PUBLISHED),
        NewsLead("테스트 기사 2", SECOND_URL, "NEWSIS", PUBLISHED),
    )
    fact = ProposedFact(
        "good-day-2-2027-h1-announcement", "ENTERTAINMENT",
        (("굿데이",), ("시즌2",), ("상반기",), ("공개 계획",)),
    )
    bodies = (BODY, BODY + " 서로 다른 테스트 기사 문장입니다.")
    observations = tuple(
        ArticleObservation(item.url, body, PUBLISHED, NOW)
        for item, body in zip(news, bodies)
    )
    # This digest represents a trusted SYNTHETIC case in the test only.
    # It does not certify a real article or turn keyword matching into truth.
    initial = assess_cross_source_evidence(
        lead, news, observations, fact, now=NOW,
    )
    assert initial.status == "REVIEW_REQUIRED"
    assert initial.evidence_ref is not None
    case = ReviewedNewsCase(
        SearchApiReviewCandidate(lead, news), fact,
        EVENT_TITLE, EVENT_SUMMARY, "예능", ARTICLE_URL,
        initial.evidence_ref,
    )
    upstream = Mock()
    upstream.trending_now.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now", "geo": "KR",
            "time": "past_24_hours",
        },
        "trends": [{
            "query": lead.query, "news_token": lead.news_token,
            "start_date": PUBLISHED.isoformat(),
            "categories": ["entertainment"], "is_active": True,
        }],
    }
    upstream.related_news.return_value = {
        "search_parameters": {
            "engine": "google_trends_trending_now_news",
            "news_token": lead.news_token,
        },
        "news": [{
            "title": item.title, "link": item.url, "source": item.publisher,
            "iso_date": PUBLISHED.isoformat(),
        } for item in news],
    }
    opener = Mock()
    opener.open.side_effect = [
        FakeArticleResponse(ARTICLE_URL, bodies[0]),
        FakeArticleResponse(
            SECOND_URL, bodies[1] + (" 변경됨" if changed_body else ""),
        ),
    ]
    bridge = SearchApiSnapshotBridge(
        upstream, case, reader_factory=lambda: ArticleReader(opener=opener),
        clock=lambda: NOW,
    )
    return bridge, opener


def approved_test_profile():
    def source(source_id):
        if source_id != SOURCE_ID:
            raise SupplyBlocked("SOURCE_NOT_APPROVED")
        return SimpleNamespace(scope=SCOPE)
    return SimpleNamespace(source=source)


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_existing_trend_api_renders_approved_shaped_news_row(
    client: TestClient, db_session: Session,
) -> None:
    """Mock source I/O, real Snapshot, MariaDB DML and API, no mocked API."""
    bridge, opener = reviewed_bridge()
    preview = bridge.collect_preview()
    assert preview is not None
    assert "test-only-token" not in str(preview)
    row = bridge.verify(preview, NOW)
    assert type(row) is NewsSnapshot
    assert ADAPTERS[SOURCE_ID].scope == SCOPE
    with pytest.raises(SupplyBlocked, match="SEARCHAPI_ROLE_NOT_BOUND"):
        ADAPTERS[SOURCE_ID].verify(preview, NOW)
    assert opener.open.call_count == 2
    row = bind_snapshot(row, policy="AUTO_V1", target="isolated-test")
    validate_snapshot_freshness(approved_test_profile(), row, NOW)

    parent = Category(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="SearchApi Contract Entertainment",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add(parent)
    db_session.flush()

    child = Category(
        category_code=None,
        category_name="예능",
        sort_order=1,
        is_active=True,
        parent_id=parent.category_id,
    )
    db_session.add(child)
    db_session.flush()

    conn = db_session.connection()
    category_id = _category_id(
        conn, row.parent_code, row.child_name, lock=True,
    )
    assert category_id == child.category_id
    assert inspect_snapshot(conn, row) == "NEW"
    trend_id = insert_trend_item(
        conn, row, category_id=category_id,
        collected_at=NOW.replace(tzinfo=None),
        summary=row.summary, is_primary=row.is_primary,
        status=row.proposed_status, platform=row.platform,
    )
    source_id = db_session.execute(
        text("SELECT source_id FROM trend_sources WHERE trend_id = :id"),
        {"id": trend_id},
    ).scalar_one()
    # Confirm the same identity is observed as duplicate by the real Writer
    # inspector, rather than incorrectly proposing a second insert.
    assert inspect_snapshot(db_session.connection(), row) == (
        "SKIP_EXISTING_RELEASE"
    )

    response = client.get("/api/trends", params={"category_id": child.category_id})
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    card = next(item for item in items if item["trend_id"] == trend_id)
    assert card["title"] == EVENT_TITLE
    assert card["summary"] == EVENT_SUMMARY
    assert card["thumbnail_url"] is None
    assert card["latest_source"] == {
        "source_id": source_id,
        "platform": "ETC",
        "source_title": None,
        "source_url": ARTICLE_URL,
    }
    assert card["categories"] == [{
        "category_id": child.category_id,
        "category_name": child.category_name,
        "parent": {
            "category_id": parent.category_id,
            "category_name": parent.category_name,
            "category_code": "ENTERTAINMENT",
        },
    }]


def test_reviewed_event_identity_uses_writer_dedupe_but_stays_hidden(
    client: TestClient, db_session: Session,
) -> None:
    """Review-only evidence can never imply ACTIVE publication authorization."""
    # Synthetic review proof: this is NOT live original-page verification.
    fact = ProposedFact(
        "good-day-2-2027-h1-announcement",
        "ENTERTAINMENT",
        (("굿데이",), ("시즌2",)),
    )
    review = CrossSourceReview(
        status="REVIEW_REQUIRED",
        reason="TWO_ARTICLE_BODIES_CONTAIN_ASSERTIONS_NOT_INDEPENDENT_PROOF",
        urls=(
            ARTICLE_URL,
            "https://mobile.newsis.com/view/NISX20261123_0003878761",
        ),
        evidence_ref=sha256(b"test-only-article-evidence").hexdigest(),
    )
    identity = build_review_event_identity(fact, review)
    assert identity is not None
    assert identity.proposed_status == "HIDDEN"
    assert identity.publish_authorization == "NONE"
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_TYPE_NOT_SUPPORTED"):
        validate_snapshot_freshness(object(), identity, datetime.now().astimezone())

    parent = Category(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="SearchApi Review-Only Parent",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    db_session.add(parent)
    db_session.flush()
    child = Category(
        category_code=None,
        category_name="SearchApi Review-Only Child",
        sort_order=1,
        is_active=True,
        parent_id=parent.category_id,
    )
    db_session.add(child)
    db_session.flush()

    # Reuse the common Writer DML inside a rollback-isolated test database.
    # Operational run_writer() is not invoked; an unapproved review item
    # must never reach the ACTIVE publication path.
    row = SimpleNamespace(
        title="SearchApi pending article review",
        normalized_title="searchapi-review-only-good-day-2027",
        external_id=identity.external_id,
        source_key=identity.source_key,
        source_url=identity.source_url,
        platform="ETC",
    )
    trend_id = insert_trend_item(
        db_session.connection(),
        row,
        category_id=child.category_id,
        collected_at=datetime(2026, 11, 23, 9, 0, 0),
        summary=None,
        is_primary=True,
        status=identity.proposed_status,
        platform="ETC",
    )
    assert inspect_snapshot(db_session.connection(), row) == (
        "SKIP_EXISTING_RELEASE"
    )
    persisted = db_session.execute(
        text("SELECT status FROM trends WHERE trend_id = :id"),
        {"id": trend_id},
    ).scalar_one()
    assert persisted == "HIDDEN"

    response = client.get("/api/trends")
    assert response.status_code == 200, response.text
    assert all(
        item["trend_id"] != trend_id
        for item in response.json()["data"]["items"]
    )


def test_reviewed_news_changed_evidence_holds():
    bridge, opener = reviewed_bridge(changed_body=True)
    preview = bridge.collect_preview()
    assert preview is not None
    with pytest.raises(SupplyBlocked, match="NEWS_REVIEWED_EVIDENCE_CHANGED"):
        bridge.verify(preview, NOW)
    assert opener.open.call_count == 2


def test_reviewed_news_rejects_tampered_preview_and_missing_scope():
    bridge, opener = reviewed_bridge()
    preview = bridge.collect_preview()
    assert preview is not None
    with pytest.raises(SupplyBlocked, match="NEWS_PREVIEW_MISMATCH"):
        bridge.verify({**preview, "title": "unreviewed"}, NOW)
    with pytest.raises(SupplyBlocked, match="STALE_PREVIEW"):
        bridge.verify(preview, NOW + timedelta(minutes=11))
    opener.open.assert_not_called()

    row = bridge.verify(preview, NOW)
    unapproved = SimpleNamespace(
        source=lambda _: SimpleNamespace(scope="UNAPPROVED"),
    )
    with pytest.raises(SupplyBlocked, match="SOURCE_SNAPSHOT_MISMATCH"):
        validate_snapshot_freshness(unapproved, row, NOW)
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_EXPIRED"):
        validate_snapshot_freshness(
            approved_test_profile(),
            replace(row, source_published_at=(NOW - timedelta(days=2)).isoformat()),
            NOW,
        )


def test_interest_card_and_expiry_use_existing_api_and_writer(
    client: TestClient, db_session: Session,
):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    topic = "관심도 검증용 작품"
    topics = {topic: ("ENTERTAINMENT", "드라마")}
    collector, writer = Mock(), Mock()
    for upstream in (collector, writer):
        upstream.trending_now.return_value = {
            "search_parameters": {
                "engine": "google_trends_trending_now",
                "geo": "KR", "time": "past_24_hours",
            },
            "trends": [{
                "query": topic, "is_active": True,
                "start_date": (now - timedelta(hours=1)).isoformat(),
                "news_token": "fixture-token", "categories": ["entertainment"],
            }],
        }
    preview = SearchInterestAdapter(
        collector, topics=topics, clock=lambda: now,
    ).collect_preview()
    assert preview is not None
    row = SearchInterestAdapter(writer, topics=topics).verify(preview, now)
    row = bind_snapshot(row, policy="AUTO_V1", target="isolated-test")
    profile = SimpleNamespace(
        source=lambda source_id: SimpleNamespace(
            scope=INTEREST_SCOPE if source_id == INTEREST_SOURCE_ID else "WRONG",
        ),
    )
    validate_snapshot_freshness(profile, row, now)
    parent = Category(
        category_code=CategoryCode.ENTERTAINMENT, category_name="Interest Parent",
        sort_order=1, is_active=True, parent_id=None,
    )
    db_session.add(parent)
    db_session.flush()
    child = Category(
        category_code=None, category_name="드라마", sort_order=1,
        is_active=True, parent_id=parent.category_id,
    )
    db_session.add(child)
    db_session.flush()
    conn = db_session.connection()
    assert _category_id(conn, row.parent_code, row.child_name, lock=True) == (
        child.category_id
    )
    assert inspect_snapshot(conn, row) == "NEW"
    trend_id = insert_trend_item(
        conn, row, category_id=child.category_id,
        collected_at=now.replace(tzinfo=None), summary=row.summary,
        is_primary=True, status="ACTIVE", platform="ETC",
    )
    assert inspect_snapshot(conn, row) == "SKIP_EXISTING_RELEASE"
    response = client.get("/api/trends", params={"category_id": child.category_id})
    assert response.status_code == 200, response.text
    card = next(
        item for item in response.json()["data"]["items"]
        if item["trend_id"] == trend_id
    )
    assert card["title"] == topic
    assert card["summary"] == row.summary
    assert card["latest_source"]["source_url"] == INTEREST_URL
    assert card["thumbnail_url"] is None
    for offset, visible in [
        (timedelta(hours=24, seconds=-1), True),
        (timedelta(hours=24), False),
    ]:
        repo = TrendRepository(db_session, utc_now=lambda: now + offset)
        ids = {item.trend_id for item in repo.find_page(
            limit=20, category_ids=[child.category_id],
            cursor_last_collected_at=None, cursor_trend_id=None,
        )}
        assert (trend_id in ids) is visible
        assert (
            trend_id in repo.find_latest_sources_by_trend_ids([trend_id])
        ) is visible
    assert inspect_snapshot(conn, row) == "SKIP_EXISTING_RELEASE"
