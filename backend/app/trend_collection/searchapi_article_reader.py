"""Bounded, nonpublishing first-party article reader for SearchApi review.

Limited to independently known publisher hosts. HTML parsing is deliberately
fail-closed; a missing body or publication date is not proof of a fact.
"""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.trend_collection.searchapi_discovery import NewsLead, TrendingLead
from app.trend_collection.searchapi_evidence import (
    ArticleObservation,
    CrossSourceReview,
    ProposedFact,
    assess_cross_source_evidence,
)

_ALLOWED_HOSTS = frozenset({"www.yna.co.kr", "mobile.newsis.com"})
_BODY_IDS = frozenset({"articlebody", "articlebodycontents", "articlebodytext"})
_BODY_CLASSES = frozenset({"article-body", "article-txt", "story-news", "view_text"})
_SKIP_TAGS = frozenset({"script", "style", "nav", "aside", "footer", "header"})
_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img",
                        "input", "link", "meta", "param", "source", "track", "wbr"})
_TIME_KEYS = frozenset({"article:published_time", "datepublished", "pubdate"})
_MAX_HTML_BYTES = 512_000
_MAX_BODY_CHARS = 32_000
_TIMEOUT = 10


class ArticleReadBlocked(RuntimeError):
    """Stable, upstream-content-free reason, never a publication exception."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ArticleReadBlocked("ARTICLE_REDIRECT_BLOCKED")


def _allow_url(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ArticleReadBlocked("ARTICLE_URL_NOT_ALLOWED")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname in _ALLOWED_HOSTS
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.query and not parsed.fragment
            and parsed.path.startswith("/view/")
            and re.fullmatch(r"/[A-Za-z0-9_./-]+", parsed.path) is not None
            and ".." not in parsed.path
        )
    except ValueError:
        valid = False
    if not valid:
        raise ArticleReadBlocked("ARTICLE_URL_NOT_ALLOWED")
    return value


def _published(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


class _ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.published: set[datetime] = set()
        self.parts: list[str] = []
        self.depth = 0
        self.skip = 0
        self.found_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = dict(attrs)
        if tag == "meta":
            key = (
                attr.get("property") or attr.get("name")
                or attr.get("itemprop") or ""
            ).lower()
            if key in _TIME_KEYS and isinstance(attr.get("content"), str):
                parsed = _published(attr["content"])
                if parsed is not None:
                    self.published.add(parsed)
        if tag == "time" and (
            (attr.get("itemprop") or "").lower() == "datepublished"
            or "published" in (attr.get("class") or "").lower()
        ) and isinstance(attr.get("datetime"), str):
            parsed = _published(attr["datetime"])
            if parsed is not None:
                self.published.add(parsed)
        if self.skip:
            if tag not in _VOID_TAGS:
                self.skip += 1
            return
        if tag in _SKIP_TAGS:
            self.skip = 1
            return
        if self.depth:
            if tag not in _VOID_TAGS:
                self.depth += 1
            return
        classes = set((attr.get("class") or "").lower().split())
        element_id = (attr.get("id") or "").lower()
        if not self.found_body and (
            tag == "article" or element_id in _BODY_IDS
            or (attr.get("itemprop") or "").lower() == "articlebody"
            or bool(classes & _BODY_CLASSES)
            or {"story-news", "article"}.issubset(classes)
        ):
            self.depth = 1
            self.found_body = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        if tag in _VOID_TAGS:
            return
        if self.skip:
            self.skip -= 1
        elif self.depth:
            self.depth -= 1

    def handle_data(self, data: str):
        if self.depth and not self.skip:
            self.parts.append(data)


def _extract_article(page: bytes, content_type: str) -> tuple[str, datetime]:
    media = content_type.split(";", 1)[0].strip().lower()
    if media not in ("text/html", "application/xhtml+xml"):
        raise ArticleReadBlocked("ARTICLE_CONTENT_TYPE_INVALID")
    params = [v.strip().lower() for v in content_type.split(";")[1:]]
    charset = next((p.split("=", 1)[1].strip(' "') for p in params
                    if p.startswith("charset=")), "utf-8")
    if charset not in ("utf-8", "euc-kr", "cp949"):
        raise ArticleReadBlocked("ARTICLE_CHARSET_UNSUPPORTED")
    try:
        html = page.decode(charset, errors="strict")
    except (LookupError, UnicodeError):
        raise ArticleReadBlocked("ARTICLE_ENCODING_INVALID") from None
    parser = _ArticleHTML()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, OverflowError):
        raise ArticleReadBlocked("ARTICLE_HTML_INVALID") from None
    body = " ".join(" ".join(parser.parts).split())
    if not 80 <= len(body) <= _MAX_BODY_CHARS:
        raise ArticleReadBlocked("ARTICLE_BODY_MISSING_OR_INVALID")
    if len(parser.published) != 1:
        raise ArticleReadBlocked("ARTICLE_PUBLISHED_TIME_UNCONFIRMED")
    return body, next(iter(parser.published))


class ArticleReader:
    """At most two specific first-party HTTPS GETs per reader instance."""

    def __init__(self, *, opener=None):
        self._opener = opener if opener is not None else build_opener(
            ProxyHandler({}), _NoRedirect(),
        )
        self._calls = 0

    def read(self, news: NewsLead, *, now: datetime) -> ArticleObservation:
        if type(news) is not NewsLead:
            raise ArticleReadBlocked("ARTICLE_INPUT_INVALID")
        return self.read_url(news.url, now=now)

    def read_url(self, source_url: str, *, now: datetime) -> ArticleObservation:
        """Standalone original-page diagnosis; does not attest SearchApi news."""
        if self._calls >= 2:
            raise ArticleReadBlocked("ARTICLE_REQUEST_BUDGET")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ArticleReadBlocked("ARTICLE_INPUT_INVALID")
        url = _allow_url(source_url)
        self._calls += 1
        request = Request(url, method="GET", headers={
            "Accept": "text/html", "User-Agent": "TrendLeader-ArticleReview/0.1",
        })
        try:
            with self._opener.open(request, timeout=_TIMEOUT) as response:
                if response.status != 200:
                    raise ArticleReadBlocked("ARTICLE_UNEXPECTED_STATUS")
                geturl = getattr(response, "geturl", None)
                result_url = (
                    geturl() if callable(geturl)
                    else getattr(response, "url", None)
                )
                if result_url != url:
                    raise ArticleReadBlocked("ARTICLE_URL_CHANGED")
                data = response.read(_MAX_HTML_BYTES + 1)
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            try:
                raise ArticleReadBlocked(f"ARTICLE_HTTP_{exc.code}") from None
            finally:
                exc.close()
        except (URLError, OSError, HTTPException):
            raise ArticleReadBlocked("ARTICLE_NETWORK_ERROR") from None
        if len(data) > _MAX_HTML_BYTES:
            raise ArticleReadBlocked("ARTICLE_SIZE_LIMIT")
        body, published_at = _extract_article(data, content_type)
        return ArticleObservation(url, body, published_at, now.astimezone(timezone.utc))


def review_news_articles(
    lead: TrendingLead,
    related_news: tuple[NewsLead, ...],
    fact: ProposedFact,
    *,
    now: datetime,
    reader: ArticleReader,
) -> CrossSourceReview:
    """Fetch two exact known articles and screen; never authorizes publication."""
    if type(related_news) is not tuple or len(related_news) != 2:
        return CrossSourceReview("HOLD", "TWO_ARTICLES_REQUIRED")
    if (
        type(lead) is not TrendingLead or type(fact) is not ProposedFact
        or not isinstance(now, datetime) or now.utcoffset() is None
        or type(reader) is not ArticleReader
        or any(type(item) is not NewsLead for item in related_news)
    ):
        return CrossSourceReview("HOLD", "INVALID_INPUT")
    # Validate both article destinations before making even the first request.
    try:
        urls = tuple(_allow_url(item.url) for item in related_news)
    except ArticleReadBlocked as exc:
        return CrossSourceReview("HOLD", str(exc))
    if len(set(urlsplit(url).hostname for url in urls)) != 2:
        return CrossSourceReview("HOLD", "SAME_PUBLISHER_ORIGIN")
    try:
        observations = tuple(reader.read(item, now=now) for item in related_news)
    except ArticleReadBlocked as exc:
        return CrossSourceReview("HOLD", str(exc))
    return assess_cross_source_evidence(
        lead, related_news, observations, fact, now=now,
    )
