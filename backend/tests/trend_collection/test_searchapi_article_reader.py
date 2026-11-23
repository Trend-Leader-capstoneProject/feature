"""Reader unit tests with fake HTTPS responses; no live article or DB access."""

from datetime import datetime, timezone
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from app.trend_collection.searchapi_article_reader import (
    ArticleReadBlocked,
    ArticleReader,
    _extract_article,
    review_news_articles,
)
from app.trend_collection.searchapi_discovery import NewsLead, TrendingLead
from app.trend_collection.searchapi_evidence import ProposedFact

NOW = datetime(2026, 11, 23, 1, tzinfo=timezone.utc)
PUBLISHED = datetime(2026, 11, 23, 0, tzinfo=timezone.utc)
YNA = "https://www.yna.co.kr/view/AKR20261123042700005"
NEWSIS = "https://mobile.newsis.com/view/NISX20261123_0003878761"
BODY = (
    "이번 발표에서 굿데이 시즌2가 2027년 상반기 공개 예정이라고 밝혔습니다. "
    "관련 프로그램에 관한 일정과 진행 사항을 설명하며 새 시즌에 대한 "
    "기대를 전했습니다. 추가 내용은 제작사 공지와 원문을 확인해야 합니다."
)


def html(body=BODY, *, date="2026-11-23T09:00:00+09:00", root="article"):
    return (
        f'<html><head><meta property="article:published_time" '
        f'content="{date}"></head><body><{root}><p>{body}</p>'
        f'<script>비밀 스크립트</script><p>{body}</p><br>'
        f'<img src="sample.jpg"></{root}>'
        f'<footer>기사 내용이 아닙니다.</footer></body></html>'
    ).encode("utf-8")


class FakeResponse:
    status = 200

    def __init__(
        self, *, url=YNA, data=None,
        content_type="text/html; charset=utf-8",
    ):
        self.url = url
        self.data = data if data is not None else html()
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, limit):
        return self.data[:limit]


def article(url=YNA):
    return NewsLead("굿데이 시즌2", url, "연합뉴스", PUBLISHED)


def reader_with(*responses):
    opener = Mock()
    opener.open.side_effect = list(responses) or [FakeResponse()]
    return ArticleReader(opener=opener), opener


def test_original_article_body_and_timestamp_extracted():
    reader, opener = reader_with(FakeResponse())
    observation = reader.read(article(), now=NOW)
    assert observation.source_url == YNA
    assert observation.published_at_utc == PUBLISHED
    assert observation.retrieved_at_utc == NOW
    assert "굿데이 시즌2" in observation.body_text
    assert "비밀 스크립트" not in observation.body_text
    assert "기사 내용이 아닙니다" not in observation.body_text
    assert opener.open.call_args.kwargs["timeout"] == 10


@pytest.mark.parametrize("url", [
    "http://www.yna.co.kr/view/AKR20261123042700005",
    "https://127.0.0.1/view/x",
    "https://user@www.yna.co.kr/view/x",
    "https://www.yna.co.kr:8080/view/x",
    "https://www.yna.co.kr/view/x?redirect=evil",
    "https://www.yna.co.kr/other/x",
    "https://www.yna.co.kr.evil.test/view/x",
    "https://evil.test/view/x",
])
def test_disallowed_url_makes_no_request(url):
    reader, opener = reader_with()
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_URL_NOT_ALLOWED"):
        reader.read(article(url), now=NOW)
    opener.open.assert_not_called()


def test_unexpected_content_type_blocked():
    reader, _ = reader_with(FakeResponse(content_type="application/pdf"))
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_CONTENT_TYPE_INVALID"):
        reader.read(article(), now=NOW)


def test_redirected_response_url_blocked():
    reader, _ = reader_with(FakeResponse(url=NEWSIS))
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_URL_CHANGED"):
        reader.read(article(), now=NOW)


def test_oversized_html_blocked():
    reader, _ = reader_with(FakeResponse(data=b"A" * 512001))
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_SIZE_LIMIT"):
        reader.read(article(), now=NOW)


def test_missing_and_ambiguous_published_time_blocked():
    bad_pages = [
        html(date="bad"),
        html().replace(
            b"</head>",
            b'<meta property="article:published_time" '
            b'content="2026-11-22T09:00:00+09:00"></head>',
        ),
    ]
    for document in bad_pages:
        reader, _ = reader_with(FakeResponse(data=document))
        with pytest.raises(
            ArticleReadBlocked, match="ARTICLE_PUBLISHED_TIME_UNCONFIRMED",
        ):
            reader.read(article(), now=NOW)


def test_metadata_only_cannot_replace_article_body():
    reader, _ = reader_with(FakeResponse(data=html(body="x")))
    with pytest.raises(
        ArticleReadBlocked, match="ARTICLE_BODY_MISSING_OR_INVALID",
    ):
        reader.read(article(), now=NOW)


def test_article_body_div_selector_supported():
    body, published = _extract_article(
        html(root='div id="articleBody"'), "text/html; charset=utf-8",
    )
    assert "굿데이 시즌2" in body
    assert published == PUBLISHED


def test_publisher_request_budget_is_two():
    reader, opener = reader_with(FakeResponse(), FakeResponse())
    reader.read(article(), now=NOW)
    reader.read(article(), now=NOW)
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_REQUEST_BUDGET"):
        reader.read(article(), now=NOW)
    assert opener.open.call_count == 2


def test_network_error_does_not_expose_upstream_details():
    opener = Mock()
    opener.open.side_effect = URLError("internal host details")
    reader = ArticleReader(opener=opener)
    with pytest.raises(ArticleReadBlocked, match="^ARTICLE_NETWORK_ERROR$"):
        reader.read(article(), now=NOW)


def test_two_article_html_bodies_reach_review_not_publication():
    second = FakeResponse(
        url=NEWSIS,
        data=html(body=BODY + " 두 번째 원문 관측 문장입니다."),
    )
    reader, opener = reader_with(FakeResponse(), second)
    lead = TrendingLead(
        "지드래곤", NOW, "test-only-token", frozenset({"ENTERTAINMENT"}),
    )
    fact = ProposedFact(
        "good-day-2027", "ENTERTAINMENT", (("굿데이",), ("시즌2",)),
    )
    news = (
        article(),
        NewsLead("굿데이2", NEWSIS, "뉴시스", PUBLISHED),
    )
    decision = review_news_articles(
        lead, news, fact, now=NOW, reader=reader,
    )
    assert decision.status == "REVIEW_REQUIRED"
    assert decision.publish_authorization == "NONE"
    assert opener.open.call_count == 2


def test_first_article_failure_stops_before_second_request():
    reader, opener = reader_with(
        FakeResponse(data=html(body="x")), FakeResponse(url=NEWSIS),
    )
    lead = TrendingLead(
        "지드래곤", NOW, "test-only", frozenset({"ENTERTAINMENT"}),
    )
    fact = ProposedFact("good-day-2027", "ENTERTAINMENT", (("굿데이",),))
    news = (article(), NewsLead("굿데이2", NEWSIS, "뉴시스", PUBLISHED))
    result = review_news_articles(
        lead, news, fact, now=NOW, reader=reader,
    )
    assert result.status == "HOLD"
    assert result.publish_authorization == "NONE"
    assert opener.open.call_count == 1

def test_invalid_second_article_url_rejected_before_network():
    reader, opener = reader_with(FakeResponse())
    fact = ProposedFact("case", "ENTERTAINMENT", (("굿데이",),))
    trend = TrendingLead("지드래곤", NOW, "token", frozenset({"ENTERTAINMENT"}))
    unsafe = NewsLead("unsafe", "https://127.0.0.1/view/a", "any", PUBLISHED)
    result = review_news_articles(
        trend, (article(), unsafe), fact, now=NOW, reader=reader,
    )
    assert result.status == "HOLD"
    assert result.reason == "ARTICLE_URL_NOT_ALLOWED"
    opener.open.assert_not_called()


def test_same_publisher_pair_rejected_before_network():
    reader, opener = reader_with(FakeResponse())
    fact = ProposedFact("case", "ENTERTAINMENT", (("굿데이",),))
    trend = TrendingLead("지드래곤", NOW, "token", frozenset({"ENTERTAINMENT"}))
    second = NewsLead(
        "duplicate", "https://www.yna.co.kr/view/OTHER", "YNA", PUBLISHED,
    )
    result = review_news_articles(
        trend, (article(), second), fact, now=NOW, reader=reader,
    )
    assert result.status == "HOLD"
    assert result.reason == "SAME_PUBLISHER_ORIGIN"
    opener.open.assert_not_called()


def test_legacy_yonhap_article_classes_are_supported():
    body, published = _extract_article(
        html(root='div class="story-news article"'),
        "text/html; charset=utf-8",
    )
    assert "굿데이 시즌2" in body
    assert published == PUBLISHED


def test_articlebody_itemprop_selector_is_supported():
    body, published = _extract_article(
        html(root='div itemprop="articleBody"'),
        "text/html; charset=utf-8",
    )
    assert "굿데이 시즌2" in body
    assert published == PUBLISHED


def test_self_closing_article_tag_cannot_capture_following_page_text():
    page = html().replace(b"<article>", b"<article/>")
    with pytest.raises(
        ArticleReadBlocked, match="ARTICLE_BODY_MISSING_OR_INVALID",
    ):
        _extract_article(page, "text/html; charset=utf-8")


def test_response_without_final_url_proof_is_rejected():
    response = FakeResponse()
    del response.url
    reader, opener = reader_with(response)
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_URL_CHANGED"):
        reader.read(article(), now=NOW)
    assert opener.open.call_count == 1


def test_geturl_is_checked_before_body_extraction():
    response = FakeResponse()
    response.geturl = lambda: NEWSIS
    reader, _ = reader_with(response)
    with pytest.raises(ArticleReadBlocked, match="ARTICLE_URL_CHANGED"):
        reader.read(article(), now=NOW)
