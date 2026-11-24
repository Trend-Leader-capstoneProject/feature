"""One bounded SearchApi discovery-to-original-page review cycle.

This is not a registered operational SourceAdapter and cannot write Trends.
Callers explicitly supply the existing SearchApi client and article reader.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from app.trend_collection.searchapi_article_reader import (
    ArticleReadBlocked,
    ArticleReader,
    _allow_url,
    prepare_review_event,
)
from app.trend_collection.searchapi_discovery import (
    NewsLead,
    TrendingLead,
    parse_related_news,
    parse_trending_now,
)
from app.trend_collection.searchapi_evidence import (
    CrossSourceReview,
    ProposedFact,
    ReviewEventIdentity,
)

MAX_NEWS_QUERIES = 2
_PRIORITY_ROOTS = frozenset({"FOOD", "FASHION", "BEAUTY", "ENTERTAINMENT"})


@dataclass(frozen=True, slots=True)
class SearchApiReviewCandidate:
    """A real candidate lead and two supported original links, not a TrendCard."""

    lead: TrendingLead
    related_news: tuple[NewsLead, NewsLead]


class SearchApiReviewPipeline:
    """Single-use, explicit and nonpublishing SearchApi review coordinator."""

    def __init__(self, client, *, reader: ArticleReader):
        if not (
            callable(getattr(client, "trending_now", None))
            and callable(getattr(client, "related_news", None))
            and type(reader) is ArticleReader
        ):
            raise TypeError("SEARCHAPI_PIPELINE_DEPENDENCY_INVALID")
        self._client = client
        self._reader = reader
        self._collected = False
        self._candidate: SearchApiReviewCandidate | None = None
        self._reviewed = False

    def collect_preview(
        self, *, now: datetime,
    ) -> SearchApiReviewCandidate | None:
        """One trending and up to two news requests, with no silent retry."""
        if self._collected:
            raise RuntimeError("SEARCHAPI_REVIEW_CYCLE_ALREADY_USED")
        self._collected = True
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("SEARCHAPI_REVIEW_CLOCK_INVALID")
        now = now.astimezone(timezone.utc)
        leads = parse_trending_now(self._client.trending_now(), now=now)
        # Game and IT already have dedicated suppliers. Preserve upstream
        # order within each group and spend the same budget on uncovered roots.
        eligible = (
            lead for lead in leads
            if lead.is_active and lead.possible_root_codes
            and timedelta(0) <= now - lead.started_at_utc <= timedelta(hours=24)
        )
        attempts = 0
        for lead in sorted(
            eligible,
            key=lambda item: not bool(item.possible_root_codes & _PRIORITY_ROOTS),
        ):
            if attempts >= MAX_NEWS_QUERIES:
                break
            attempts += 1
            news = parse_related_news(
                self._client.related_news(lead.news_token), now=now,
            )
            supported: list[NewsLead] = []
            publisher_hosts: set[str] = set()
            for item in news:
                try:
                    _allow_url(item.url)
                except ArticleReadBlocked:
                    continue
                host = urlsplit(item.url).hostname
                if host in publisher_hosts:
                    continue
                supported.append(item)
                if host is not None:
                    publisher_hosts.add(host)
                if len(supported) == 2:
                    self._candidate = SearchApiReviewCandidate(
                        lead, (supported[0], supported[1]),
                    )
                    return self._candidate
        return None

    def review(
        self,
        candidate: SearchApiReviewCandidate,
        fact: ProposedFact,
        *,
        now: datetime,
    ) -> tuple[CrossSourceReview, ReviewEventIdentity | None]:
        """Only the collected candidate can be reviewed, at most once."""
        if (
            self._reviewed
            or self._candidate is None
            or candidate is not self._candidate
            or type(fact) is not ProposedFact
            or fact.root_code not in candidate.lead.possible_root_codes
        ):
            return CrossSourceReview("HOLD", "CANDIDATE_NOT_REVIEWABLE"), None
        self._reviewed = True
        return prepare_review_event(
            candidate.lead, candidate.related_news, fact,
            now=now, reader=self._reader,
        )
