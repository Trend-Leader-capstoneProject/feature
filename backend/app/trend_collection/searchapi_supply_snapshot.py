"""Reviewed news event -> common Writer snapshot, without registration.

A trusted, independently content-reviewed case is an explicit prerequisite.
The collector envelope cannot supply the case, its fact or its review digest.
No trusted case source or automatic semantic approval is installed here.
"""

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
from app.trend_collection.searchapi_evidence import (
    ProposedFact,
    assess_cross_source_evidence,
    build_review_event_identity,
)
from app.trend_collection.searchapi_review_pipeline import (
    SearchApiReviewCandidate,
    SearchApiReviewPipeline,
)
from app.trend_collection.supply_adapter import SupplyBlocked, utc

SOURCE_ID = "searchapi-kr-reviewed-news"
SCOPE = "SEARCHAPI_REVIEWED_NEWS_V1"
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

    def __init__(self, client, case: ReviewedNewsCase, *, reader_factory=ArticleReader):
        if type(case) is not ReviewedNewsCase:
            raise SupplyBlocked("REVIEWED_CASE_REQUIRED")
        self._case = case
        self._client = client
        self._reader_factory = reader_factory

    def collect_preview(self) -> dict | None:
        now = datetime.now(timezone.utc)
        candidate = SearchApiReviewPipeline(
            self._client, reader=self._reader_factory(),
        ).collect_preview(now=now)
        if candidate is None:
            return None
        case = self._case
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
