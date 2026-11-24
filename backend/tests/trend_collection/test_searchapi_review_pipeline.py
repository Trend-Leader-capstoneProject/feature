"""One real-shaped discovery-to-review path; all upstream I/O is fake."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.trend_collection.searchapi_article_reader import ArticleReader
from app.trend_collection.searchapi_evidence import ProposedFact
from app.trend_collection.searchapi_review_pipeline import (
    SearchApiReviewPipeline,
)

NOW = datetime(2026, 11, 23, 10, tzinfo=timezone.utc)
YNA = "https://www.yna.co.kr/view/AKR20261123042700005"
NEWSIS = "https://mobile.newsis.com/view/NISX20261123_0003878761"
PUBLISHED = "2026-11-23T09:00:00Z"
BODY = (
    "굿데이 시즌2 제작 소식이 공개됐습니다. 제작진의 새 프로젝트에 "
    "관한 내용이 발표되었으며 세부 일정은 추가 안내될 예정입니다. "
    "이 본문은 자동 게시를 승인하지 않는 오프라인 테스트 문장입니다."
)


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, body):
        self._url = url
        self._data = (
            '<html><head><meta property="article:published_time" '
            'content="2026-11-23T09:00:00+00:00"></head><body>'
            f'<article><p>{body}</p><p>{body}</p></article>'
            '</body></html>'
        ).encode("utf-8")

    def geturl(self):
        return self._url

    def read(self, limit):
        return self._data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeSearchApi:
    def __init__(self, *, no_supported_news=False):
        self.trending_calls = 0
        self.news_calls = []
        self.no_supported_news = no_supported_news

    def trending_now(self):
        self.trending_calls += 1
        return {
            "search_parameters": {
                "engine": "google_trends_trending_now",
                "geo": "KR", "time": "past_24_hours",
            },
            "trends": [{
                "query": "지드래곤",
                "news_token": "fake-token",
                "start_date": PUBLISHED,
                "categories": ["entertainment"],
                "is_active": True,
            }],
        }

    def related_news(self, token):
        self.news_calls.append(token)
        urls = (
            ("https://other.example.com/story", NEWSIS)
            if self.no_supported_news else (YNA, NEWSIS)
        )
        return {
            "search_parameters": {
                "engine": "google_trends_trending_now_news",
            },
            "news": [
                {
                    "title": "굿데이 시즌2",
                    "link": url, "source": "신문",
                    "iso_date": PUBLISHED,
                } for url in urls
            ],
        }


def pipeline(*, no_supported_news=False):
    api = FakeSearchApi(no_supported_news=no_supported_news)
    opener = Mock()
    opener.open.side_effect = [
        FakeResponse(YNA, BODY),
        FakeResponse(NEWSIS, BODY + " 기사별로 다른 내용입니다."),
    ]
    return SearchApiReviewPipeline(api, reader=ArticleReader(opener=opener)), (
        api, opener,
    )


def _fact():
    return ProposedFact(
        "good-day-2-2027-h1-announcement", "ENTERTAINMENT",
        (("굿데이",), ("시즌2",)),
    )


def test_one_candidate_flows_to_review_without_writer_or_publication():
    coordinator, (api, opener) = pipeline()
    candidate = coordinator.collect_preview(now=NOW)
    assert candidate is not None
    assert len(candidate.related_news) == 2
    assert api.trending_calls == 1
    assert api.news_calls == ["fake-token"]
    assert opener.open.call_count == 0

    review, identity = coordinator.review(candidate, _fact(), now=NOW)
    assert review.status == "REVIEW_REQUIRED"
    assert review.publish_authorization == "NONE"
    assert identity is not None
    assert identity.external_id == (
        "searchapi-event:good-day-2-2027-h1-announcement"
    )
    assert identity.proposed_status == "HIDDEN"
    assert identity.publish_authorization == "NONE"
    assert opener.open.call_count == 2


def test_review_is_single_use_without_new_requests():
    coordinator, (_, opener) = pipeline()
    candidate = coordinator.collect_preview(now=NOW)
    assert candidate is not None
    coordinator.review(candidate, _fact(), now=NOW)
    result, identity = coordinator.review(candidate, _fact(), now=NOW)
    assert result.status == "HOLD"
    assert identity is None
    assert opener.open.call_count == 2
    with pytest.raises(RuntimeError, match="CYCLE_ALREADY_USED"):
        coordinator.collect_preview(now=NOW)


def test_unsupported_publisher_does_not_fabricate_review_candidate():
    coordinator, (api, opener) = pipeline(no_supported_news=True)
    assert coordinator.collect_preview(now=NOW) is None
    assert api.trending_calls == 1
    assert api.news_calls == ["fake-token"]
    opener.open.assert_not_called()


def test_wrong_root_is_rejected_without_reader_requests():
    coordinator, (_, opener) = pipeline()
    candidate = coordinator.collect_preview(now=NOW)
    assert candidate is not None
    invalid = ProposedFact(
        "good-day-2-2027-h1-announcement", "GAME", (("굿데이",),),
    )
    result, identity = coordinator.review(candidate, invalid, now=NOW)
    assert result.status == "HOLD"
    assert identity is None
    opener.open.assert_not_called()
