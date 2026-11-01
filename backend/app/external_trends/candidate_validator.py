
"""RSS 합성 Fixture용 P3 후보 검증. 외부 I/O 없음."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .normalizer import normalize_source_url, normalize_title
from .types import (
    CandidateDecision,
    CandidateEvaluation,
    NormalizedSource,
    ParsedCandidate,
    ReasonCode,
    SourceIssue,
    SourceIssueCode,
)


class TopicScope(StrEnum):
    CLEAR_OUT_OF_SCOPE = "CLEAR_OUT_OF_SCOPE"
    POSSIBLE_IN_SCOPE = "POSSIBLE_IN_SCOPE"
    AMBIGUOUS = "AMBIGUOUS"


class TopicRules(Protocol):
    def classify(self, normalized_title: str) -> TopicScope: ...


def evaluate_topic_gate(
    candidate: ParsedCandidate,
    topic_rules: TopicRules,
) -> CandidateEvaluation | None:
    """명백한 범위 밖만 조기 제외한다. None은 2차 검사 계속을 의미한다."""
    title = normalize_title(candidate.raw_title)

    if title is None:
        return None

    if topic_rules.classify(title.normalized_title) != TopicScope.CLEAR_OUT_OF_SCOPE:
        return None

    return CandidateEvaluation(
        decision=CandidateDecision.SKIPPED,
        reason_codes=(ReasonCode.OUT_OF_SCOPE,),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=(),
    )

def evaluate_candidate(
    candidate: ParsedCandidate,
    topic_rules: TopicRules,
    second_stage: Callable[[ParsedCandidate], CandidateEvaluation],
) -> CandidateEvaluation:
    """1차에서 제외하지 않은 후보만 2차 검증 함수로 전달한다."""
    early_result = evaluate_topic_gate(candidate, topic_rules)

    if early_result is not None:
        return early_result

    return second_stage(candidate)


# ---------------------------------------------------------------------
# V-03: Source 검증 정책과 중간 결과
# ---------------------------------------------------------------------


class DomainStatus(StrEnum):
    APPROVED = "APPROVED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class DomainPolicy:
    """정확한 hostname 일치로 출처 상태를 판정한다."""

    approved_hosts: frozenset[str]
    blocked_hosts: frozenset[str]

    def classify(self, hostname: str) -> DomainStatus:
        if hostname in self.blocked_hosts:
            return DomainStatus.BLOCKED
        if hostname in self.approved_hosts:
            return DomainStatus.APPROVED
        return DomainStatus.UNKNOWN


class SourceRelevance(StrEnum):
    RELATED = "RELATED"
    UNRELATED = "UNRELATED"
    UNCLEAR = "UNCLEAR"


class SourceRelevanceRules(Protocol):
    def classify(
        self,
        normalized_topic: str,
        normalized_source_title: str,
    ) -> SourceRelevance: ...


@dataclass(frozen=True, slots=True)
class SourceScreeningResult:
    """Source별 검증 결과. 최종 CandidateEvaluation은 아니다."""

    valid_sources: tuple[NormalizedSource, ...]
    source_issues: tuple[SourceIssue, ...]


def screen_candidate_sources(
    candidate: ParsedCandidate,
    domain_policy: DomainPolicy,
    relevance_rules: SourceRelevanceRules,
) -> SourceScreeningResult:
    """검증 가능한 Source만 유지하고 개별 문제를 기록한다."""
    topic_title = normalize_title(candidate.raw_title)

    if topic_title is None:
        return SourceScreeningResult(
            valid_sources=(),
            source_issues=(),
        )

    valid_sources: list[NormalizedSource] = []
    source_issues: list[SourceIssue] = []

    for source in candidate.source_candidates:
        article_title = (
            normalize_title(source.raw_title)
            if source.raw_title is not None
            else None
        )

        if article_title is None:
            code = (
                SourceIssueCode.SOURCE_TITLE_MISSING
                if source.raw_title is None
                else SourceIssueCode.SOURCE_TITLE_INVALID
            )
            source_issues.append(
                SourceIssue(source.item_news_index, code)
            )
            continue

        url = (
            normalize_source_url(source.raw_url)
            if source.raw_url is not None
            else None
        )

        if url is None:
            source_issues.append(
                SourceIssue(
                    source.item_news_index,
                    SourceIssueCode.SOURCE_URL_INVALID,
                )
            )
            continue

        domain_status = domain_policy.classify(url.hostname)

        if domain_status != DomainStatus.APPROVED:
            code = (
                SourceIssueCode.BLOCKED_SOURCE_DOMAIN
                if domain_status == DomainStatus.BLOCKED
                else SourceIssueCode.UNKNOWN_SOURCE_DOMAIN
            )
            source_issues.append(
                SourceIssue(source.item_news_index, code)
            )
            continue

        relevance = relevance_rules.classify(
            topic_title.normalized_title,
            article_title.normalized_title,
        )

        if relevance != SourceRelevance.RELATED:
            code = (
                SourceIssueCode.SOURCE_UNRELATED
                if relevance == SourceRelevance.UNRELATED
                else SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR
            )
            source_issues.append(
                SourceIssue(source.item_news_index, code)
            )
            continue

        valid_sources.append(
            NormalizedSource(
                source_title=article_title.display_title,
                canonical_url=url.canonical_url,
                source_key=url.source_key,
                publisher_name=source.publisher_name,
            )
        )

    return SourceScreeningResult(
        valid_sources=tuple(valid_sources),
        source_issues=tuple(source_issues),
    )



# ---------------------------------------------------------------------
# V-04: 미확인 도메인만 존재하는 후보 보류
# ---------------------------------------------------------------------


def evaluate_unknown_domain_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
) -> CandidateEvaluation | None:
    """미확인 도메인만 존재할 때 최종 DEFERRED 결과를 생성한다."""
    if screening.valid_sources:
        return None

    if not screening.source_issues:
        return None

    if any(
        issue.code != SourceIssueCode.UNKNOWN_SOURCE_DOMAIN
        for issue in screening.source_issues
    ):
        return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        return None

    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(
            ReasonCode.NO_ELIGIBLE_SOURCE,
            ReasonCode.UNKNOWN_SOURCE_DOMAIN,
        ),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )


# ---------------------------------------------------------------------
# V-05: Source 부재·필수 정보 오류에 따른 DEFERRED
# ---------------------------------------------------------------------


_METADATA_INVALID_SOURCE_CODES = frozenset(
    {
        SourceIssueCode.SOURCE_TITLE_MISSING,
        SourceIssueCode.SOURCE_TITLE_INVALID,
        SourceIssueCode.SOURCE_URL_INVALID,
    }
)


def evaluate_missing_or_invalid_source_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
) -> CandidateEvaluation | None:
    """Source가 없거나 필수 정보 오류만 있을 때 보류한다."""
    if screening.valid_sources:
        return None

    if not candidate.source_candidates:
        # Source가 없으므로 SourceIssue도 없어야 한다.
        if screening.source_issues:
            return None
    else:
        # 모든 Source가 개별 오류로 설명되는지 확인한다.
        if len(screening.source_issues) != len(candidate.source_candidates):
            return None

        if any(
            issue.code not in _METADATA_INVALID_SOURCE_CODES
            for issue in screening.source_issues
        ):
            return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        return None

    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.NO_ELIGIBLE_SOURCE,),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )


# ---------------------------------------------------------------------
# V-06: CategoryCatalog 및 활성 Child 선택 검증
# ---------------------------------------------------------------------


class ValidationExecutionError(ValueError):
    """주입된 검증 정책이나 CategoryCatalog의 설정 오류."""


@dataclass(frozen=True, slots=True)
class CategoryRoot:
    category_id: int
    code: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CategoryChild:
    category_id: int
    parent_id: int
    name: str
    is_active: bool



@dataclass(frozen=True, slots=True)
class CategoryCatalog:
    """DB 접근 없는 Root/Child Category 정책 값 객체."""

    roots: tuple[CategoryRoot, ...]
    children: tuple[CategoryChild, ...]

    def __post_init__(self) -> None:
        """중복 ID·Root 코드 및 잘못된 부모 참조를 거부한다."""
        root_ids = [root.category_id for root in self.roots]
        root_codes = [root.code for root in self.roots]
        child_ids = [child.category_id for child in self.children]

        if (
            len(root_ids) != len(set(root_ids))
            or len(root_codes) != len(set(root_codes))
            or len(child_ids) != len(set(child_ids))
            or set(root_ids).intersection(child_ids)
        ):
            raise ValidationExecutionError(
                "duplicate category identifier or root code"
            )

        known_root_ids = set(root_ids)

        if any(
            child.parent_id not in known_root_ids
            for child in self.children
        ):
            raise ValidationExecutionError(
                "child references unknown parent root"
            )

    def select_active_child_ids(
        self,
        evidence_child_ids: tuple[int, ...],
    ) -> tuple[int, ...] | None:
        """근거로 제시된 활성 Child만 중복 없이 오름차순 반환한다."""
        if not evidence_child_ids:
            return None

        roots_by_id = {
            root.category_id: root
            for root in self.roots
        }
        children_by_id = {
            child.category_id: child
            for child in self.children
        }

        selected_ids: set[int] = set()

        for child_id in evidence_child_ids:
            child = children_by_id.get(child_id)

            if child is None or not child.is_active:
                return None

            parent = roots_by_id[child.parent_id]

            if not parent.is_active:
                return None

            selected_ids.add(child_id)

        return tuple(sorted(selected_ids))


# ---------------------------------------------------------------------
# V-07: 사건 일관성 검증 및 모호한 사건 보류
# ---------------------------------------------------------------------


class EventConsistency(StrEnum):
    CONSISTENT = "CONSISTENT"
    AMBIGUOUS = "AMBIGUOUS"
    UNDETERMINED = "UNDETERMINED"


class EventConsistencyRules(Protocol):
    def assess(
        self,
        candidate: ParsedCandidate,
        screening: SourceScreeningResult,
    ) -> EventConsistency: ...




def evaluate_event_consistency_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
    event_rules: EventConsistencyRules,
) -> CandidateEvaluation | None:
    """적합 Source가 존재해도 사건 일관성이 불명확하면 보류한다."""
    # Source가 없거나 모두 부적합한 경우는 V-04·V-05 등에서 판정한다.
    if not screening.valid_sources:
        return None

    assessment = event_rules.assess(candidate, screening)

    if assessment == EventConsistency.CONSISTENT:
        # 아직 WOULD_ACCEPT가 아니다. Category 등 후속 검증이 필요하다.
        return None

    if assessment not in (
        EventConsistency.AMBIGUOUS,
        EventConsistency.UNDETERMINED,
    ):
        raise ValidationExecutionError(
            "invalid event consistency policy result"
        )

    title = normalize_title(candidate.raw_title)

    if title is None:
        raise ValidationExecutionError(
            "eligible source exists with invalid candidate title"
        )

    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.EVENT_AMBIGUOUS,),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )


# ---------------------------------------------------------------------
# V-08: 관련성 근거 부족에 따른 DEFERRED
# ---------------------------------------------------------------------



def evaluate_relevance_unclear_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
) -> CandidateEvaluation | None:
    """모든 Source의 관련성 근거가 부족한 경우에만 보류한다."""
    if screening.valid_sources:
        return None

    if not candidate.source_candidates:
        return None

    if len(screening.source_issues) != len(candidate.source_candidates):
        return None

    if any(
        issue.code != SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR
        for issue in screening.source_issues
    ):
        return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        return None

    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(
            ReasonCode.NO_ELIGIBLE_SOURCE,
            ReasonCode.RELEVANCE_UNCLEAR,
        ),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )
