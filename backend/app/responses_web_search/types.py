"""S0 내부 계약. SDK·DB·공개 API 타입과 독립적이다."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class SearchRunConfig:
    profile: str = "IT_DIGITAL"
    lookback_days: int = 7
    max_candidates: int = 3
    max_tool_calls: int = 1
    fixture_reference_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if (
            self.profile != "IT_DIGITAL"
            or type(self.lookback_days) is not int
            or self.lookback_days != 7
            or type(self.max_candidates) is not int
            or not 1 <= self.max_candidates <= 3
            or type(self.max_tool_calls) is not int
            or self.max_tool_calls != 1
        ):
            raise ValueError("invalid S0 fixture configuration")
        anchor = self.fixture_reference_at_utc
        if anchor is not None and (
            not isinstance(anchor, datetime)
            or anchor.tzinfo is None
            or anchor.utcoffset() != timedelta(0)
        ):
            raise ValueError("fixture reference must be an aware UTC datetime")


@dataclass(frozen=True, slots=True)
class ParsedResponse:
    status: str | None
    tool_calls_observed: int = 0
    simulated_web_search_executed: bool = False
    reason_codes: tuple[str, ...] = ()
    candidates: tuple[dict[str, object], ...] = ()
    citation_urls: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    topic_draft: str
    source_url: str
    source_title_reference: str


@dataclass(frozen=True, slots=True)
class CandidateIssue:
    candidate_index: int
    code: str
