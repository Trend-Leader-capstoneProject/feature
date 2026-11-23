"""Strict, nonpublishing cross-source evidence checks for SearchApi leads.

News titles, SearchApi publisher labels and keyword category hints are NOT
independently verified facts. This module accepts article-body observations
from a separate original-page reader; it never fetches, stores or publishes.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unicodedata import normalize
from urllib.parse import urlsplit

from app.trend_collection.searchapi_discovery import (
    NewsLead,
    TrendingLead,
    _safe_public_url,
)

MAX_ARTICLE_CHARS = 32_000
MAX_ASSERTION_GROUPS = 8
RECENT_OBSERVATION = timedelta(minutes=10)
# Review observation bound only, NOT publication TTL.
MAX_NEWS_AGE_FOR_REVIEW = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class ArticleObservation:
    """Article body extracted from the original publisher page by a reader.

    Caller must retain its acquisition/provenance checks separately. Merely
    constructing this value does not attest to authentic source retrieval.
    """

    source_url: str
    body_text: str
    published_at_utc: datetime
    retrieved_at_utc: datetime


@dataclass(frozen=True, slots=True)
class ProposedFact:
    """Fixed fact proposition; NEVER generated directly from SearchApi title."""

    review_case_key: str
    root_code: str
    # Each group holds alternate text expressions for one required claim.
    # Checking phrases is a *screen*, not semantic or independent fact proof.
    assertion_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class CrossSourceReview:
    status: str
    reason: str
    urls: tuple[str, ...] = ()
    evidence_ref: str | None = None

    @property
    def publish_authorization(self) -> str:
        return "NONE"


def _publisher_group(value: str) -> str | None:
    if _safe_public_url(value) is None:
        return None
    host = urlsplit(value).hostname
    if host is None:
        return None
    labels = host.lower().split(".")
    if len(labels) < 2 or any(not part for part in labels):
        return None
    # Only a grouping heuristic: two DNS sites do not prove editorial
    # independence or disprove common syndicated press-release content.
    if len(labels) >= 3 and labels[-2:] in (
        ["co", "kr"], ["or", "kr"], ["ne", "kr"], ["go", "kr"],
    ):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _normalized(value: str) -> str:
    return " ".join(normalize("NFKC", value).casefold().split())


def _invalid_claim(fact: ProposedFact, lead: TrendingLead) -> bool:
    if (
        type(fact) is not ProposedFact
        or not isinstance(fact.review_case_key, str)
        or not 1 <= len(fact.review_case_key) <= 120
        or any(not (char.isascii() and (
            char.isalnum() or char in "_:-"
        )) for char in fact.review_case_key)
        or fact.root_code not in lead.possible_root_codes
        or not 1 <= len(fact.assertion_groups) <= MAX_ASSERTION_GROUPS
    ):
        return True
    for group in fact.assertion_groups:
        if (
            type(group) is not tuple or not 1 <= len(group) <= 6
            or any(
                not isinstance(part, str)
                or not 2 <= len(part) <= 80
                or not part.strip()
                or any(ord(c) < 32 for c in part)
                for part in group
            )
        ):
            return True
    return False


def assess_cross_source_evidence(
    lead: TrendingLead,
    related_news: tuple[NewsLead, ...],
    observations: tuple[ArticleObservation, ...],
    fact: ProposedFact,
    *,
    now: datetime,
) -> CrossSourceReview:
    """Screen two distinct original-article bodies; always requires review.

    This is deliberately NOT an operational SourceAdapter.verify(): matching
    words in two pages cannot establish truth, editorial independence, rights
    or safe automatic publication. Raw SearchApi news alone always HOLDs.
    """
    def hold(reason: str) -> CrossSourceReview:
        return CrossSourceReview("HOLD", reason)

    if (
        not isinstance(now, datetime) or now.utcoffset() is None
        or type(lead) is not TrendingLead
        or type(related_news) is not tuple
        or type(observations) is not tuple
    ):
        return hold("INVALID_INPUT")
    now = now.astimezone(timezone.utc)
    if _invalid_claim(fact, lead):
        return hold("INVALID_FACT_PROPOSAL")
    if len(observations) != 2:
        return hold("TWO_ORIGINAL_ARTICLES_REQUIRED")
    # Do not let a caller manufacture additional related-news references.
    if any(type(article) is not NewsLead for article in related_news):
        return hold("INVALID_NEWS_METADATA")
    news_by_url = {item.url: item for item in related_news}
    if len(news_by_url) != len(related_news):
        return hold("DUPLICATED_NEWS_METADATA")

    origins: set[str] = set()
    texts: list[str] = []
    accepted_urls: list[str] = []
    body_digests: list[tuple[str, str, str]] = []
    for observation in observations:
        if type(observation) is not ArticleObservation:
            return hold("ORIGINAL_ARTICLE_REQUIRED")
        url = observation.source_url
        matching = news_by_url.get(url)
        origin = _publisher_group(url)
        if matching is None or origin is None:
            return hold("ARTICLE_LINK_NOT_IN_NEWS")
        if origin in origins:
            return hold("SAME_PUBLISHER_ORIGIN")
        origins.add(origin)
        for timestamp in (
            observation.published_at_utc, observation.retrieved_at_utc,
            matching.published_at_utc,
        ):
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                return hold("INVALID_EVIDENCE_TIME")
        age = now - observation.retrieved_at_utc.astimezone(timezone.utc)
        news_age = now - observation.published_at_utc.astimezone(timezone.utc)
        metadata_difference = abs(
            observation.published_at_utc - matching.published_at_utc
        )
        if (
            not timedelta(0) <= age <= RECENT_OBSERVATION
            or not timedelta(0) <= news_age <= MAX_NEWS_AGE_FOR_REVIEW
            or metadata_difference > timedelta(days=1)
        ):
            return hold("EVIDENCE_STALE_OR_TIME_MISMATCH")
        body = observation.body_text
        if (
            not isinstance(body, str) or not 80 <= len(body) <= MAX_ARTICLE_CHARS
            or any(ord(ch) == 0 for ch in body)
        ):
            return hold("ORIGINAL_ARTICLE_BODY_REQUIRED")
        normalized = _normalized(body)
        if not all(
            any(_normalized(phrase) in normalized for phrase in group)
            for group in fact.assertion_groups
        ):
            return hold("FACT_NOT_SUPPORTED_IN_ARTICLE_BODY")
        texts.append(normalized)
        accepted_urls.append(url)
        body_digests.append((
            url,
            observation.published_at_utc.astimezone(timezone.utc).isoformat(),
            sha256(normalized.encode("utf-8")).hexdigest(),
        ))

    if texts[0] == texts[1]:
        return hold("IDENTICAL_REPRINT")
    urls = tuple(sorted(accepted_urls))
    # Evidence digest must change when original-page content changes. This is
    # an audit fingerprint, NOT a stable event/source identity or approval.
    evidence_ref = sha256(json.dumps(
        {"case": fact.review_case_key, "articles": sorted(body_digests)},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return CrossSourceReview(
        "REVIEW_REQUIRED",
        "TWO_ARTICLE_BODIES_CONTAIN_ASSERTIONS_NOT_INDEPENDENT_PROOF",
        urls,
        evidence_ref,
    )
