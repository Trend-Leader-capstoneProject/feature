"""Optional news references; no publication authority, DB or scheduler I/O."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unicodedata import normalize
from urllib.parse import urlsplit

from app.external_trends.normalizer import extract_candidate_hostname
from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.searchapi_client import SearchApiClientError
from app.trend_collection.searchapi_discovery import (
    SearchApiDiscoveryError,
    TrendingLead,
    parse_related_news,
)

WINDOW = timedelta(hours=48)
_PATH = re.compile(r"/[A-Za-z0-9._~/-]+")
_MAX_ARTICLES = 2


@dataclass(frozen=True, slots=True)
class ArticleLinkRule:
    """Trusted operator scope, not evidence that rights have been verified."""

    host: str
    path_prefix: str
    publisher: str
    evidence_ref: str
    allow_title: bool = False


@dataclass(frozen=True, slots=True)
class RelatedArticle:
    url: str
    url_key: str
    publisher: str
    title: str | None
    published_at_utc: str
    selection_order: int


@dataclass(frozen=True, slots=True)
class RelatedNewsResult:
    articles: tuple[RelatedArticle, ...] = ()
    status: str = "DISABLED"
    retry_not_before: int | None = None


def _valid_path(path: str) -> bool:
    return (
        _PATH.fullmatch(path) is not None
        and all(part not in {"", ".", ".."} for part in path[1:].split("/"))
    )


def _valid_rule(rule: ArticleLinkRule) -> bool:
    return (
        isinstance(rule, ArticleLinkRule)
        and isinstance(rule.host, str)
        and rule.host.isascii()
        and rule.host == rule.host.lower()
        and not rule.host.endswith((".local", ".internal"))
        and extract_candidate_hostname(f"https://{rule.host}") == rule.host
        and isinstance(rule.path_prefix, str)
        and rule.path_prefix.endswith("/")
        and _valid_path(rule.path_prefix[:-1])
        and isinstance(rule.publisher, str)
        and 1 <= len(rule.publisher) <= 255
        and rule.publisher == rule.publisher.strip()
        and isinstance(rule.evidence_ref, str)
        and 1 <= len(rule.evidence_ref.strip()) <= 512
        and type(rule.allow_title) is bool
    )


def _canonical_url(url: str, rule: ArticleLinkRule) -> str | None:
    # The minimal scope intentionally excludes query-dependent article URLs.
    # No fetch or redirect resolution is performed for publisher links.
    if (
        "?" in url or "#" in url or not url.startswith("https://")
        or extract_candidate_hostname(url) != rule.host
    ):
        return None
    parts = urlsplit(url)
    if (
        parts.netloc.lower() not in {rule.host, f"{rule.host}:443"}
        or not _valid_path(parts.path)
        or not parts.path.startswith(rule.path_prefix)
        or any(part.lower() in {"redirect", "goto", "out", "forward"}
               for part in parts.path.split("/"))
    ):
        return None
    return f"https://{rule.host}{parts.path}"


def _topic_key(value: str) -> str:
    return "".join(normalize("NFC", value).casefold().split())


def select_related_articles(
    payload: object, *, lead: TrendingLead, now: datetime,
    rules: tuple[ArticleLinkRule, ...] = (),
) -> tuple[RelatedArticle, ...]:
    """Select reference links from one verified lead's matching News response."""
    if not rules or not all(_valid_rule(rule) for rule in rules):
        return ()
    if now.utcoffset() is None:
        raise SearchApiDiscoveryError("INVALID_CLOCK")
    now = now.astimezone(timezone.utc)
    if not isinstance(payload, dict):
        raise SearchApiDiscoveryError("INVALID_NEWS_RESPONSE")
    params = payload.get("search_parameters")
    if not isinstance(params, dict) or params.get("news_token") != lead.news_token:
        raise SearchApiDiscoveryError("NEWS_TOKEN_MISMATCH")

    topic = _topic_key(lead.query)
    candidates = []
    seen = set()
    for item in parse_related_news(payload, now=now):
        if (
            len(topic) < 2 or topic not in _topic_key(item.title)
            or not timedelta(0) <= now - item.published_at_utc < WINDOW
        ):
            continue
        matches = [
            (rule, url)
            for rule in rules
            if rule.publisher == item.publisher
            and (url := _canonical_url(item.url, rule)) is not None
        ]
        # Ambiguous scope must never expand permission.
        if len(matches) != 1:
            continue
        rule, url = matches[0]
        if url in seen:
            continue
        seen.add(url)
        candidates.append((rule, url, item))

    # First eligible link, then a distinct publisher if available.
    chosen = candidates[:1]
    if len(candidates) > 1:
        first = candidates[0][0].publisher
        second = next(
            (entry for entry in candidates[1:] if entry[0].publisher != first),
            candidates[1],
        )
        chosen.append(second)
    return tuple(
        RelatedArticle(
            url=url, url_key=sha256(url.encode()).hexdigest(),
            publisher=rule.publisher,
            title=item.title if rule.allow_title else None,
            published_at_utc=item.published_at_utc.isoformat(),
            selection_order=index,
        )
        for index, (rule, url, item) in enumerate(chosen[:_MAX_ARTICLES], 1)
    )


def fetch_related_articles(
    client, *, lead: TrendingLead, now: datetime,
    rules: tuple[ArticleLinkRule, ...] = (),
) -> RelatedNewsResult:
    """One optional request, only for a caller's independently verified lead.

    The caller must bind trusted rules under the approved 3-request profile.
    This helper does not itself activate that profile or perform any DB writes.
    """
    if not rules or not all(_valid_rule(rule) for rule in rules):
        return RelatedNewsResult()
    try:
        articles = select_related_articles(
            client.related_news(lead.news_token), lead=lead, now=now, rules=rules,
        )
    except RateLimited as exc:
        # Preserve the deadline for the scheduler; do not retry or pretend
        # the required observation failed.
        return RelatedNewsResult(
            status="RATE_LIMITED", retry_not_before=exc.retry_not_before,
        )
    except (SearchApiClientError, SearchApiDiscoveryError):
        return RelatedNewsResult(status="UNAVAILABLE")
    return RelatedNewsResult(
        articles=articles, status="AVAILABLE" if articles else "EMPTY",
    )
