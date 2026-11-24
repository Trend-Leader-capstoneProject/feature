"""Reviewed news event -> common Writer snapshot, without registration.

A trusted, independently content-reviewed case is an explicit prerequisite.
The collector envelope cannot supply the case, its fact or its review digest.
A bounded attributed-report adapter is bound only through approved roles.
The registry descriptor alone confers no publication authority.
"""

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from app.external_trends.normalizer import normalize_title
from app.trend_collection.publication_policy import (
    POLICY_VERSION,
    PROFILE,
    _digest,
)
from app.trend_collection.searchapi_article_reader import (
    ArticleReadBlocked,
    ArticleReader,
    _allow_url,
)
from app.trend_collection.searchapi_discovery import NewsLead, TrendingLead
from app.trend_collection.searchapi_evidence import (
    ArticleObservation,
    ProposedFact,
    assess_cross_source_evidence,
    build_review_event_identity,
)
from app.trend_collection.searchapi_review_pipeline import (
    SearchApiReviewCandidate,
    SearchApiReviewPipeline,
)
from app.trend_collection.supply_adapter import (
    SEARCHAPI_SCOPE,
    SEARCHAPI_SOURCE_ID,
    SupplyBlocked,
    utc,
)

SOURCE_ID = SEARCHAPI_SOURCE_ID
SCOPE = SEARCHAPI_SCOPE
UNBOUND = "UNBOUND_OPERATIONAL"
# Conservative admission ceiling for the isolated 24-hour discovery contract.
# This is not an approved operational retention or display TTL.
NEWS_WINDOW = timedelta(hours=24)
PREVIEW_WINDOW = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class NewsSnapshot:
    """Concrete common Writer contract; distinct from review-only identity."""

    profile_id: str
    policy_version: str
    target: str
    candidate_identity: str
    evidence_ref: str
    title: str
    normalized_title: str
    summary: str
    source_url: str
    external_id: str
    source_key: str
    platform: str
    parent_code: str
    child_name: str
    observed_at_utc: str
    source_published_at: str
    proposed_status: str
    is_primary: bool = True
    thumbnail_url: None = None
    source_title: None = None

    @property
    def content_digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class ReviewedNewsCase:
    """Trusted caller's explicit reviewed content, not collector input.

    Only an independent content review may supply this value. Constructing
    it is not proof of review, source rights, G6 or an operational profile.
    The candidate's upstream token is never emitted in the preview.
    """

    candidate: SearchApiReviewCandidate = field(repr=False)
    fact: ProposedFact
    title: str
    summary: str
    child_name: str
    primary_url: str
    reviewed_evidence_ref: str


def _preview(candidate, case_key: str, observed: datetime) -> dict:
    return {
        "case_key": case_key,
        "query": candidate.lead.query,
        "started_at_utc": candidate.lead.started_at_utc.isoformat(),
        "urls": sorted(item.url for item in candidate.related_news),
        "observed_at_utc": observed.astimezone(timezone.utc).isoformat(),
    }


class SearchApiSnapshotBridge:
    """Independent re-read and exact reviewed-evidence binding.

    This bridge can be exercised with a trusted test case. It is deliberately
    absent from ADAPTERS; per-event review sourcing, rights, egress policy,
    and final freshness policy must be resolved before operational use.
    """

    scope = SCOPE

    def __init__(
        self, client, case: ReviewedNewsCase, *,
        reader_factory=ArticleReader, clock=None,
    ):
        if (
            type(case) is not ReviewedNewsCase
            or type(case.candidate) is not SearchApiReviewCandidate
            or type(case.fact) is not ProposedFact
        ):
            raise SupplyBlocked("REVIEWED_CASE_REQUIRED")
        self._case = case
        self._client = client
        self._reader_factory = reader_factory
        self._clock = clock if clock is not None else (
            lambda: datetime.now(timezone.utc)
        )

    def collect_preview(self) -> dict | None:
        now = self._clock()
        candidate = SearchApiReviewPipeline(
            self._client, reader=self._reader_factory(),
        ).collect_preview(now=now)
        case = self._case
        if (
            candidate is None
            or case.fact.root_code not in candidate.lead.possible_root_codes
        ):
            return None
        preview = _preview(candidate, case.fact.review_case_key, now)
        if preview != _preview(case.candidate, case.fact.review_case_key, now):
            return None
        return preview

    def verify(self, preview: dict, now: datetime) -> NewsSnapshot:
        case = self._case
        if (
            type(preview) is not dict or not isinstance(now, datetime)
            or now.utcoffset() is None
        ):
            raise SupplyBlocked("INVALID_NEWS_PREVIEW")
        now = now.astimezone(timezone.utc)
        observed = utc(preview.get("observed_at_utc"))
        if not timedelta(0) <= now - observed <= PREVIEW_WINDOW:
            raise SupplyBlocked("STALE_PREVIEW")
        expected = _preview(case.candidate, case.fact.review_case_key, observed)
        if preview != expected:
            raise SupplyBlocked("NEWS_PREVIEW_MISMATCH")
        lead = case.candidate.lead
        if (
            not lead.is_active
            or not timedelta(0) <= now - lead.started_at_utc <= NEWS_WINDOW
            or case.fact.root_code not in lead.possible_root_codes
        ):
            raise SupplyBlocked("NEWS_DISCOVERY_STALE_OR_MISMATCHED")

        news = case.candidate.related_news
        try:
            urls = tuple(_allow_url(item.url) for item in news)
        except ArticleReadBlocked:
            raise SupplyBlocked("NEWS_SOURCE_NOT_ALLOWED") from None
        if (
            len(urls) != 2
            or len({urlsplit(url).hostname for url in urls}) != 2
            or case.primary_url not in urls
        ):
            raise SupplyBlocked("NEWS_SOURCE_NOT_ALLOWED")

        # An exact independent re-read is necessary even for a reviewed case.
        # The collector supplies no title, summary, category or approval.
        reader = self._reader_factory()
        try:
            observations = tuple(reader.read(item, now=now) for item in news)
        except ArticleReadBlocked:
            raise SupplyBlocked("NEWS_DETAIL_UNAVAILABLE") from None
        return _snapshot_from_review(case, observations, observed, now)


def _snapshot_from_review(
    case: ReviewedNewsCase,
    observations: tuple[ArticleObservation, ...],
    observed: datetime,
    now: datetime,
) -> NewsSnapshot:
    lead, news = case.candidate.lead, case.candidate.related_news
    review = assess_cross_source_evidence(
        lead, news, observations, case.fact, now=now,
    )
    identity = build_review_event_identity(case.fact, review)
    if (
        identity is None
        or identity.evidence_ref != case.reviewed_evidence_ref
    ):
        raise SupplyBlocked("NEWS_REVIEWED_EVIDENCE_CHANGED")
    earliest = min(item.published_at_utc for item in observations)
    if not timedelta(0) <= now - earliest <= NEWS_WINDOW:
        raise SupplyBlocked("NEWS_ARTICLE_EXPIRED")
    title = normalize_title(case.title)
    if (
        title is None or not isinstance(case.summary, str)
        or not 1 <= len(case.summary.strip()) <= 1000
        or not isinstance(case.child_name, str)
        or not 1 <= len(case.child_name.strip()) <= 255
    ):
        raise SupplyBlocked("NEWS_PRESENTATION_INVALID")
    # The common Writer resolves and locks the actual active category;
    # neither the collector nor this snapshot may invent a category ID.
    return NewsSnapshot(
        profile_id=PROFILE,
        policy_version=POLICY_VERSION,
        target=UNBOUND,
        candidate_identity=identity.candidate_identity,
        evidence_ref=_digest({
            "reviewed_evidence": identity.evidence_ref,
            "fact": asdict(case.fact),
            "title": title.display_title,
            "summary": case.summary,
            "child": case.child_name,
            "primary_url": case.primary_url,
        }),
        title=title.display_title,
        normalized_title=title.normalized_title,
        summary=case.summary,
        source_url=case.primary_url,
        external_id=identity.external_id,
        source_key=identity.source_key,
        platform="ETC",
        parent_code=case.fact.root_code,
        child_name=case.child_name,
        observed_at_utc=observed.isoformat(),
        source_published_at=earliest.astimezone(timezone.utc).isoformat(),
        proposed_status="ACTIVE",
    )


# Explicit labels from category_master.py; no guessed IDs or fallback category.
_EVENT_CATEGORIES = {
    "의류": ("FASHION", "의류"),
    "신발": ("FASHION", "신발"),
    "가방": ("FASHION", "가방"),
    "향수": ("BEAUTY", "향수"),
    "스킨케어": ("BEAUTY", "스킨케어"),
    "메이크업": ("BEAUTY", "메이크업"),
    "식품": ("FOOD", "식품·음료"),
    "음료": ("FOOD", "식품·음료"),
    "예능": ("ENTERTAINMENT", "예능"),
    "영화": ("ENTERTAINMENT", "영화"),
    "드라마": ("ENTERTAINMENT", "드라마"),
}
_EVENT_ROOTS = frozenset(root for root, _ in _EVENT_CATEGORIES.values())
_EVENT = re.compile(
    r"(?P<actor>[가-힣A-Za-z0-9][가-힣A-Za-z0-9 ·&-]{1,39}?)"
    r"(?:은|는|이|가) (?P<kind>" + "|".join(_EVENT_CATEGORIES) + r") "
    r"""['"‘“](?P<item>[가-힣A-Za-z0-9][가-힣A-Za-z0-9 ·&-]{1,59})['"’”]"""
    r"(?:을|를) (?P<verb>출시했다|공개했다|발표했다)\."
)
_EVENT_LABEL = {"출시했다": "출시", "공개했다": "공개", "발표했다": "발표"}
# Narrow positive-clause extraction is not general semantic verification.
_DISPUTED = re.compile(
    r"사실무근|오보|정정|루머|의혹|부인|취소|철회|아니다|않았다|거짓|허위|가정"
)


def _reported_events(body: str) -> set[tuple[str, str, str, str]]:
    normalized = " ".join(body.split())
    if _DISPUTED.search(normalized):
        return set()
    events = set()
    for sentence in re.split(r"(?<=[.!?]) +", normalized):
        match = _EVENT.fullmatch(sentence)
        if match:
            events.add((
                match["actor"], match["kind"], match["item"], match["verb"],
            ))
    return events


def build_automatic_reviewed_case(
    candidate: SearchApiReviewCandidate,
    observations: tuple[ArticleObservation, ...],
    *,
    now: datetime,
) -> ReviewedNewsCase | None:
    """Construct an attributed report, not independent truth certification.

    Both originals must report the same explicitly named event in a supported
    affirmative clause. No guessed classification, article copy, or rights grant.
    """
    if (
        type(candidate) is not SearchApiReviewCandidate
        or len(observations) != 2
        or any(type(obs) is not ArticleObservation for obs in observations)
        or not isinstance(now, datetime) or now.utcoffset() is None
    ):
        return None
    lead = candidate.lead
    if (
        not lead.is_active
        or not timedelta(0) <= now - lead.started_at_utc <= NEWS_WINDOW
    ):
        return None
    left, right = (_reported_events(obs.body_text) for obs in observations)
    if len(left) != 1 or left != right:
        return None
    actor, kind, item, verb = next(iter(left))
    root, child = _EVENT_CATEGORIES[kind]
    if root not in lead.possible_root_codes:
        return None
    action = _EVENT_LABEL[verb]
    # MVP identity: named entity and event, not a search term, URL or timestamp.
    key = _digest([actor.casefold(), root, child, item.casefold(), action])
    fact = ProposedFact(key, root, ((actor,), (kind,), (item,), (verb,)))
    review = assess_cross_source_evidence(
        lead, candidate.related_news, observations, fact, now=now,
    )
    if review.status != "REVIEW_REQUIRED" or review.evidence_ref is None:
        return None
    if any(
        not timedelta(0) <= now - obs.published_at_utc <= NEWS_WINDOW
        for obs in observations
    ):
        return None
    return ReviewedNewsCase(
        candidate=candidate,
        fact=fact,
        title=f"{actor} {item} {action} 소식",
        summary=f"두 매체가 {actor}의 {kind} {item} {action} 소식을 보도했습니다.",
        child_name=child,
        primary_url=review.urls[0],
        reviewed_evidence_ref=review.evidence_ref,
    )


def _automatic_preview(case: ReviewedNewsCase, observed: datetime) -> dict:
    lead = case.candidate.lead
    return {
        "case_key": case.fact.review_case_key,
        "evidence_ref": case.reviewed_evidence_ref,
        "observed_at_utc": observed.astimezone(timezone.utc).isoformat(),
        "started_at_utc": lead.started_at_utc.isoformat(),
        "roots": sorted(lead.possible_root_codes & _EVENT_ROOTS),
        "news": [
            {"url": item.url, "published_at_utc": item.published_at_utc.isoformat()}
            for item in sorted(case.candidate.related_news, key=lambda n: n.url)
        ],
    }


class AutomaticSearchApiAdapter:
    """Bounded automatic path; role binding and approval remain separate.

    Collector alone uses SearchApi (existing three-call ceiling). Writer reads
    both original pages itself and derives the event and category anew.
    Discovery hints cannot authorize a fact or expand the allowed categories.
    """

    scope = SCOPE

    def __init__(self, client=None, *, reader_factory=ArticleReader, clock=None):
        self._client = client
        self._reader_factory = reader_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def collect_preview(self) -> dict | None:
        if self._client is None:
            raise SupplyBlocked("SEARCHAPI_COLLECTOR_REQUIRED")
        now = self._clock()
        reader = self._reader_factory()
        candidate = SearchApiReviewPipeline(
            self._client, reader=reader,
        ).collect_preview(now=now)
        if candidate is None or not candidate.lead.possible_root_codes & _EVENT_ROOTS:
            return None
        try:
            observations = tuple(
                reader.read(item, now=now) for item in candidate.related_news
            )
        except ArticleReadBlocked:
            return None
        case = build_automatic_reviewed_case(candidate, observations, now=now)
        return _automatic_preview(case, now) if case is not None else None

    def verify(self, preview: dict, now: datetime) -> NewsSnapshot:
        if (
            not isinstance(now, datetime) or now.utcoffset() is None
            or type(preview) is not dict or set(preview) != {
                "case_key", "evidence_ref", "observed_at_utc", "started_at_utc",
                "roots", "news",
            }
            or any(
                not isinstance(preview[key], str)
                or re.fullmatch(r"[a-f0-9]{64}", preview[key]) is None
                for key in ("case_key", "evidence_ref")
            )
        ):
            raise SupplyBlocked("INVALID_NEWS_PREVIEW")
        now = now.astimezone(timezone.utc)
        observed = utc(preview["observed_at_utc"])
        started = utc(preview["started_at_utc"])
        if not timedelta(0) <= now - observed <= PREVIEW_WINDOW:
            raise SupplyBlocked("STALE_PREVIEW")
        if not timedelta(0) <= now - started <= NEWS_WINDOW:
            raise SupplyBlocked("NEWS_DISCOVERY_STALE_OR_MISMATCHED")
        roots, raw_news = preview["roots"], preview["news"]
        if (
            type(roots) is not list or not roots
            or any(type(root) is not str or root not in _EVENT_ROOTS for root in roots)
            or roots != sorted(set(roots))
            or type(raw_news) is not list or len(raw_news) != 2
            or any(type(item) is not dict or set(item) != {
                "url", "published_at_utc",
            } for item in raw_news)
        ):
            raise SupplyBlocked("INVALID_NEWS_PREVIEW")
        try:
            # These metadata objects deliberately omit title, publisher and
            # token. None of those fields is used as evidence by the Writer.
            news = tuple(
                NewsLead(
                    "", _allow_url(item["url"]), "", utc(item["published_at_utc"]),
                )
                for item in raw_news
            )
        except ArticleReadBlocked:
            raise SupplyBlocked("NEWS_SOURCE_NOT_ALLOWED") from None
        if len({urlsplit(item.url).hostname for item in news}) != 2:
            raise SupplyBlocked("NEWS_SOURCE_NOT_ALLOWED")
        lead = TrendingLead("", started, "", frozenset(roots))
        candidate = SearchApiReviewCandidate(lead, news)
        reader = self._reader_factory()
        try:
            observations = tuple(reader.read(item, now=now) for item in news)
        except ArticleReadBlocked:
            raise SupplyBlocked("NEWS_DETAIL_UNAVAILABLE") from None
        case = build_automatic_reviewed_case(candidate, observations, now=now)
        if case is None or _automatic_preview(case, observed) != preview:
            raise SupplyBlocked("NEWS_REVIEWED_EVIDENCE_CHANGED")
        return _snapshot_from_review(case, observations, observed, now)
