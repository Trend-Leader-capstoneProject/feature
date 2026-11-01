"""외부 트렌드 Parser의 영속성 비의존 출력 계약."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class WarningCode(StrEnum):
    INVALID_PUB_DATE = "INVALID_PUB_DATE"


class ItemIssueCode(StrEnum):
    MISSING_ITEM_TITLE = "MISSING_ITEM_TITLE"


@dataclass(frozen=True, slots=True)
class ParsedSource:
    item_news_index: int
    raw_title: str | None
    raw_url: str | None
    publisher_name: str | None


@dataclass(frozen=True, slots=True)
class ParsedCandidate:
    item_index: int
    raw_title: str
    rss_published_at: datetime | None
    source_candidates: tuple[ParsedSource, ...]
    warnings: tuple[WarningCode, ...]


@dataclass(frozen=True, slots=True)
class ItemIssue:
    item_index: int
    code: ItemIssueCode


@dataclass(frozen=True, slots=True)
class ParsedFeed:
    candidates: tuple[ParsedCandidate, ...]
    item_issues: tuple[ItemIssue, ...]



# ---------------------------------------------------------------------
# P3: 후보 검증 결과 타입
# ---------------------------------------------------------------------


class CandidateDecision(StrEnum):
    WOULD_ACCEPT = "WOULD_ACCEPT"
    DEFERRED = "DEFERRED"
    SKIPPED = "SKIPPED"


class ReasonCode(StrEnum):
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    NO_ELIGIBLE_SOURCE = "NO_ELIGIBLE_SOURCE"
    UNKNOWN_SOURCE_DOMAIN = "UNKNOWN_SOURCE_DOMAIN"
    EVENT_AMBIGUOUS = "EVENT_AMBIGUOUS"
    RELEVANCE_UNCLEAR = "RELEVANCE_UNCLEAR"


class SourceIssueCode(StrEnum):
    SOURCE_TITLE_MISSING = "SOURCE_TITLE_MISSING"
    SOURCE_URL_INVALID = "SOURCE_URL_INVALID"
    BLOCKED_SOURCE_DOMAIN = "BLOCKED_SOURCE_DOMAIN"
    UNKNOWN_SOURCE_DOMAIN = "UNKNOWN_SOURCE_DOMAIN"
    SOURCE_UNRELATED = "SOURCE_UNRELATED"
    DUPLICATE_SOURCE = "DUPLICATE_SOURCE"
    SOURCE_TITLE_INVALID = "SOURCE_TITLE_INVALID"
    SOURCE_RELEVANCE_UNCLEAR = "SOURCE_RELEVANCE_UNCLEAR"


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    source_title: str
    canonical_url: str
    source_key: str
    publisher_name: str | None


@dataclass(frozen=True, slots=True)
class SourceIssue:
    item_news_index: int
    code: SourceIssueCode


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    decision: CandidateDecision
    reason_codes: tuple[ReasonCode, ...]
    normalized_title: str | None
    valid_sources: tuple[NormalizedSource, ...]
    category_ids: tuple[int, ...]
    warnings: tuple[WarningCode, ...]
    source_issues: tuple[SourceIssue, ...]
