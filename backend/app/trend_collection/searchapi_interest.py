"""Google Trends observation adapter; no operational approval or DB access.

The trusted topic catalog is injected by the caller, never by a preview.
Collector and Writer must have independently bound clients and catalogs.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
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
from app.trend_collection.supply_adapter import (
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

    @property
    def content_digest(self) -> str:
        return _digest(asdict(self))


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
    ):
        if not callable(getattr(client, "trending_now", None)):
            raise SupplyBlocked("INTEREST_CLIENT_REQUIRED")
        self._client = client
        self._topics = dict(topics)
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

    def _eligible(self, lead: TrendingLead, now: datetime) -> bool:
        category = self._topics.get(lead.query)
        return (
            category is not None
            and category[0] in lead.possible_root_codes
            and lead.is_active
            and timedelta(0) <= now - lead.started_at_utc <= WINDOW
        )

    @staticmethod
    def _preview(lead: TrendingLead, observed: datetime) -> dict:
        return {
            "source_id": SOURCE_ID,
            "scope": SCOPE,
            "case_key": _case_key(lead.query),
            "query": lead.query,
            "started_at_utc": lead.started_at_utc.isoformat(),
            "observed_at_utc": observed.isoformat(),
        }

    def collect_preview(self) -> dict | None:
        now = _clock(self._clock())
        leads = parse_trending_now(self._client.trending_now(), now=now)
        for lead in leads:
            if self._eligible(lead, now):
                return self._preview(lead, now)
        return None

    def verify(self, preview: dict, now: datetime) -> InterestSnapshot:
        now = _clock(now)
        if (
            type(preview) is not dict or set(preview) != {
                "source_id", "scope", "case_key", "query",
                "started_at_utc", "observed_at_utc",
            }
            or preview["source_id"] != SOURCE_ID or preview["scope"] != SCOPE
            or not isinstance(preview["query"], str)
            or preview["query"] not in self._topics
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
        leads = parse_trending_now(self._client.trending_now(), now=now)
        for lead in leads:
            if (
                self._eligible(lead, now)
                and self._preview(lead, observed) == preview
            ):
                return self._snapshot(lead, now)
        raise SupplyBlocked("INTEREST_OBSERVATION_UNCONFIRMED")

    def _snapshot(self, lead: TrendingLead, now: datetime) -> InterestSnapshot:
        title = normalize_title(lead.query)
        if title is None:
            raise SupplyBlocked("INTEREST_TOPIC_INVALID")
        parent, child = self._topics[lead.query]
        identity = "searchapi-interest:" + _case_key(lead.query)
        return InterestSnapshot(
            profile_id=PROFILE,
            policy_version=POLICY_VERSION,
            target="UNBOUND_OPERATIONAL",
            candidate_identity=identity,
            evidence_ref=_digest({
                "scope": SCOPE, "query": lead.query,
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
