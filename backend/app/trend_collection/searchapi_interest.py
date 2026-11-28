"""Google Trends observation adapter; no operational approval or DB access.

The trusted topic catalog is injected by the caller, never by a preview.
Collector and Writer must have independently bound clients and catalogs.
"""

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.external_trends.normalizer import normalize_title
from app.trend_collection.publication_policy import (
    POLICY_VERSION,
    PROFILE,
    _digest,
)
from app.trend_collection.searchapi_discovery import (
    TrendingLead,
    parse_trending_now,
)
from app.trend_collection.searchapi_interest_classifier import (
    BLOCKED,
    MODIFIERS,
    RULES,
    VERSION as CLASSIFIER_VERSION,
    classify,
)
from app.trend_collection.searchapi_related_articles import (
    ArticleLinkRule,
    RelatedArticle,
    RelatedNewsResult,
    fetch_related_articles,
)
from app.trend_collection.supply_adapter import (
    INTEREST_HYBRID_SCOPE,
    INTEREST_SCOPE,
    INTEREST_SOURCE_ID,
    SupplyBlocked,
    utc,
)

SOURCE_ID = INTEREST_SOURCE_ID
SCOPE = INTEREST_SCOPE
SOURCE_URL = "https://trends.google.com/trending?geo=KR&hl=ko&hours=24"
WINDOW = timedelta(hours=24)
PREVIEW_WINDOW = timedelta(minutes=10)
ROOTS = frozenset({"FOOD", "FASHION", "BEAUTY", "ENTERTAINMENT"})


@dataclass(frozen=True, slots=True)
class InterestSnapshot:
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
    started_at_utc: str
    proposed_status: str
    is_primary: bool = True
    thumbnail_url: None = None
    source_title: None = None
    related_articles: tuple[RelatedArticle, ...] = ()

    @property
    def content_digest(self) -> str:
        payload = asdict(self)
        if not self.related_articles:
            # Preserve the existing observation-only digest.
            payload.pop("related_articles")
        return _digest(payload)


def _clock(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise SupplyBlocked("INTEREST_CLOCK_INVALID")
    return now.astimezone(timezone.utc)


def _case_key(query: str) -> str:
    title = normalize_title(query)
    if title is None:
        raise SupplyBlocked("INTEREST_TOPIC_INVALID")
    # One subject per existing unique-title / source identity contract.
    return _digest(["KR", title.normalized_title])


class SearchInterestAdapter:
    """Only an active, catalogued query is eligible; no event inference."""

    scope = SCOPE

    def __init__(
        self, client, *, topics: Mapping[str, tuple[str, str]], clock=None,
        allow_missing_news_token: bool = False, hybrid: bool = False,
    ):
        if not callable(getattr(client, "trending_now", None)):
            raise SupplyBlocked("INTEREST_CLIENT_REQUIRED")
        self._client = client
        self._topics = dict(topics)
        self._hybrid = hybrid
        self.scope = INTEREST_HYBRID_SCOPE if hybrid else SCOPE
        self._allow_missing_news_token = allow_missing_news_token or hybrid
        self.diagnostics: dict[str, int] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        for query, category in self._topics.items():
            if (
                not isinstance(query, str) or not query
                or normalize_title(query) is None
                or type(category) is not tuple or len(category) != 2
                or not isinstance(category[0], str) or category[0] not in ROOTS
                or not isinstance(category[1], str)
                or not 1 <= len(category[1].strip()) <= 255
            ):
                raise SupplyBlocked("INTEREST_CATALOG_INVALID")
        self._policy_ref = _digest({
            "version": CLASSIFIER_VERSION,
            "catalog": self._topics,
            "rules": sorted((list(pair), terms) for pair, terms in RULES.items()),
            "modifiers": sorted(MODIFIERS),
            "blocked": sorted(BLOCKED),
        }) if hybrid else None

    def _eligible(self, lead: TrendingLead, now: datetime) -> bool:
        if self._hybrid:
            return (
                lead.is_active and timedelta(0) <= now - lead.started_at_utc <= WINDOW
                and classify(lead, self._topics).eligible
            )
        category = self._topics.get(lead.query)
        return (
            category is not None
            and category[0] in lead.possible_root_codes
            and lead.is_active
            and timedelta(0) <= now - lead.started_at_utc <= WINDOW
        )

    def _preview(self, lead: TrendingLead, observed: datetime) -> dict:
        preview = {
            "source_id": SOURCE_ID,
            "scope": self.scope,
            "case_key": _case_key(lead.query),
            "query": lead.query,
            "started_at_utc": lead.started_at_utc.isoformat(),
            "observed_at_utc": observed.isoformat(),
        }
        if self._hybrid:
            decision = classify(lead, self._topics)
            preview["classification"] = asdict(decision)
            preview["classification"]["rule_ids"] = list(decision.rule_ids)
            preview["classification_policy_ref"] = self._policy_ref
        return preview

    def collect_preview(self, *, after_case_key=None) -> dict | None:
        if after_case_key is not None and (
            not self._hybrid or not isinstance(after_case_key, str)
            or re.fullmatch(r"[a-f0-9]{64}", after_case_key) is None
        ):
            raise SupplyBlocked("INTEREST_CURSOR_INVALID")
        now = _clock(self._clock())
        leads = parse_trending_now(
            self._client.trending_now(), now=now,
            allow_missing_news_token=self._allow_missing_news_token,
            interest_only=self._hybrid,
        )
        if not self._hybrid:
            for lead in leads:
                if self._eligible(lead, now):
                    return self._preview(lead, now)
            return None
        eligible = []
        counts = Counter()
        for lead in leads:
            decision = classify(lead, self._topics)
            counts[decision.method if decision.eligible else decision.reason_code] += 1
            if decision.eligible:
                eligible.append(lead)
        self.diagnostics = {"examined": len(leads), "eligible": len(eligible), **counts}
        if not eligible:
            return None
        index = next((
            i + 1 for i, lead in enumerate(eligible)
            if _case_key(lead.query) == after_case_key
        ), 0)
        return self._preview(eligible[index % len(eligible)], now)

    def verify(self, preview: dict, now: datetime) -> InterestSnapshot:
        now = _clock(now)
        return self._snapshot(self._verified_lead(preview, now), now)

    def verify_with_news(
        self, preview: dict, now: datetime, *, rules: tuple[ArticleLinkRule, ...],
    ) -> tuple[InterestSnapshot, RelatedNewsResult]:
        """Caller must bind the independently approved Writer scope."""
        if self._hybrid:
            raise SupplyBlocked("ARTICLE_SCOPE_NOT_APPROVED")
        now = _clock(now)
        lead = self._verified_lead(preview, now)
        snapshot = self._snapshot(lead, now)
        news = fetch_related_articles(self._client, lead=lead, now=now, rules=rules)
        return replace(snapshot, related_articles=news.articles), news

    def _verified_lead(self, preview: dict, now: datetime) -> TrendingLead:
        now = _clock(now)
        keys = {
            "source_id", "scope", "case_key", "query",
            "started_at_utc", "observed_at_utc",
        }
        if self._hybrid:
            keys |= {"classification", "classification_policy_ref"}
        if (
            type(preview) is not dict or set(preview) != keys
            or preview["source_id"] != SOURCE_ID or preview["scope"] != self.scope
            or not isinstance(preview["query"], str)
            or (not self._hybrid and preview["query"] not in self._topics)
            or (self._hybrid and preview["classification_policy_ref"] != self._policy_ref)
            or preview["case_key"] != _case_key(preview["query"])
        ):
            raise SupplyBlocked("INTEREST_PREVIEW_INVALID")
        observed = utc(preview["observed_at_utc"])
        started = utc(preview["started_at_utc"])
        if (
            not timedelta(0) <= now - observed <= PREVIEW_WINDOW
            or not timedelta(0) <= now - started <= WINDOW
            or started > observed
        ):
            raise SupplyBlocked("INTEREST_PREVIEW_EXPIRED")
        # The Writer fetches the observation itself, not the collector's
        # claimed ranking, title, category, token or raw provider response.
        leads = parse_trending_now(
            self._client.trending_now(), now=now,
            allow_missing_news_token=self._allow_missing_news_token,
            interest_only=self._hybrid,
        )
        for lead in leads:
            if (
                self._eligible(lead, now)
                and self._preview(lead, observed) == preview
            ):
                return lead
        raise SupplyBlocked("INTEREST_OBSERVATION_UNCONFIRMED")

    def _snapshot(self, lead: TrendingLead, now: datetime) -> InterestSnapshot:
        title = normalize_title(lead.query)
        if title is None:
            raise SupplyBlocked("INTEREST_TOPIC_INVALID")
        if self._hybrid:
            decision = classify(lead, self._topics)
            if not decision.eligible:
                raise SupplyBlocked("INTEREST_CLASSIFICATION_UNCONFIRMED")
            parent, child = decision.parent_code, decision.child_name
        else:
            parent, child = self._topics[lead.query]
        identity = "searchapi-interest:" + _case_key(lead.query)
        return InterestSnapshot(
            profile_id=PROFILE,
            policy_version=POLICY_VERSION,
            target="UNBOUND_OPERATIONAL",
            candidate_identity=identity,
            evidence_ref=_digest({
                "scope": self.scope, "query": lead.query,
                **({"classification_policy_ref": self._policy_ref} if self._hybrid else {}),
                "started_at": lead.started_at_utc.isoformat(),
                "observed_at": now.isoformat(),
                "category": [parent, child],
            }),
            title=title.display_title,
            normalized_title=title.normalized_title,
            summary=(
                "한국의 최근 24시간 Google 급상승 검색어로 확인된 주제입니다. "
                "데이터 출처: Google Trends (SearchApi 경유)."
            ),
            source_url=SOURCE_URL,
            external_id=identity,
            source_key=sha256(f"ETC:{identity}".encode()).hexdigest(),
            platform="ETC",
            parent_code=parent,
            child_name=child,
            observed_at_utc=now.isoformat(),
            started_at_utc=lead.started_at_utc.isoformat(),
            proposed_status="ACTIVE",
        )
