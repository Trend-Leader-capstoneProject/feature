
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


class ArticleTopicScopeRules(Protocol):
    """승인·관련성 검증을 통과한 기사별 범위 판단 정책."""

    def classify(
        self,
        normalized_topic: str,
        normalized_source_title: str,
    ) -> TopicScope: ...



def evaluate_topic_gate(
    candidate: ParsedCandidate,
    topic_rules: TopicRules,
) -> CandidateEvaluation | None:
    """명백한 범위 밖만 조기 제외한다.

    None은 2차 검사 계속을 의미한다.
    """
    title = normalize_title(candidate.raw_title)

    # 정규화 실패 시 조기 제외하지 않는다.
    # 최종 Validator에서 별도로 처리한다.
    if title is None:
        return None

    scope = topic_rules.classify(title.normalized_title)

    # 잘못된 정책 반환값을 정상 판정으로 취급하지 않는다.
    if not isinstance(scope, TopicScope):
        raise ValidationExecutionError(
            "invalid topic scope policy result"
        )

    # 명백한 범위 밖이 아니라면 2차 검증으로 진행한다.
    if scope != TopicScope.CLEAR_OUT_OF_SCOPE:
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
    seen_source_keys: set[str] = set()

    for source in candidate.source_candidates:
        # ---------------------------------------------------------
        # 1. 기사 제목 검증
        # ---------------------------------------------------------
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
                SourceIssue(
                    source.item_news_index,
                    code,
                )
            )
            continue

        # ---------------------------------------------------------
        # 2. URL 안전성 및 정규화
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 3. 도메인 승인 정책 검증
        # ---------------------------------------------------------
        domain_status = domain_policy.classify(url.hostname)

        if not isinstance(domain_status, DomainStatus):
            raise ValidationExecutionError(
                "invalid domain policy result"
            )

        if domain_status != DomainStatus.APPROVED:
            code = (
                SourceIssueCode.BLOCKED_SOURCE_DOMAIN
                if domain_status == DomainStatus.BLOCKED
                else SourceIssueCode.UNKNOWN_SOURCE_DOMAIN
            )
            source_issues.append(
                SourceIssue(
                    source.item_news_index,
                    code,
                )
            )
            continue

        # ---------------------------------------------------------
        # 4. 검색어와 기사 제목의 명시적 관련성 검증
        # ---------------------------------------------------------
        relevance = relevance_rules.classify(
            topic_title.normalized_title,
            article_title.normalized_title,
        )

        if not isinstance(relevance, SourceRelevance):
            raise ValidationExecutionError(
                "invalid source relevance policy result"
            )

        if relevance != SourceRelevance.RELATED:
            code = (
                SourceIssueCode.SOURCE_UNRELATED
                if relevance == SourceRelevance.UNRELATED
                else SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR
            )
            source_issues.append(
                SourceIssue(
                    source.item_news_index,
                    code,
                )
            )
            continue

        # ---------------------------------------------------------
        # 5. 동일 source_key 중복 제거 (V-18)
        # ---------------------------------------------------------
        if url.source_key in seen_source_keys:
            source_issues.append(
                SourceIssue(
                    source.item_news_index,
                    SourceIssueCode.DUPLICATE_SOURCE,
                )
            )
            continue

        seen_source_keys.add(url.source_key)

        # ---------------------------------------------------------
        # 6. 모든 조건을 통과한 Source만 유지
        # ---------------------------------------------------------
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
        """정책 데이터 타입·중복·부모 참조를 검증한다."""

        # R-04A: 컬렉션 자체의 계약 검증
        if (
            not isinstance(self.roots, tuple)
            or not isinstance(self.children, tuple)
        ):
            raise ValidationExecutionError(
                "invalid category catalog collection type"
            )

        # R-04A: Root 값 객체와 필드 타입 검증
        for root in self.roots:
            if (
                not isinstance(root, CategoryRoot)
                or type(root.category_id) is not int
                or not isinstance(root.code, str)
                or type(root.is_active) is not bool
            ):
                raise ValidationExecutionError(
                    "invalid category catalog root data"
                )

        # R-04A: Child 값 객체와 필드 타입 검증
        for child in self.children:
            if (
                not isinstance(child, CategoryChild)
                or type(child.category_id) is not int
                or type(child.parent_id) is not int
                or not isinstance(child.name, str)
                or type(child.is_active) is not bool
            ):
                raise ValidationExecutionError(
                    "invalid category catalog child data"
                )

        # 기존 V-06: 식별자 및 Root 코드 중복 검증
        root_ids = [
            root.category_id
            for root in self.roots
        ]
        root_codes = [
            root.code
            for root in self.roots
        ]
        child_ids = [
            child.category_id
            for child in self.children
        ]

        if (
            len(root_ids) != len(set(root_ids))
            or len(root_codes) != len(set(root_codes))
            or len(child_ids) != len(set(child_ids))
            or set(root_ids).intersection(child_ids)
        ):
            raise ValidationExecutionError(
                "duplicate category identifier or root code"
            )

        # 기존 V-06: Child의 부모 Root 참조 검증
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



class CategoryEvidenceRules(Protocol):
    """검증된 기사 근거로 지원 가능한 Child ID를 판정한다."""

    def supported_child_ids(
        self,
        normalized_title: str,
        valid_sources: tuple[NormalizedSource, ...],
    ) -> tuple[int, ...] | None: ...



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
    """적합 Source의 사건 일관성이 불명확하면 보류한다."""
    if not screening.valid_sources:
        return None

    assessment = event_rules.assess(candidate, screening)

    # StrEnum은 일반 문자열과 값 비교가 가능하므로
    # 반드시 Enum 타입부터 확인한다.
    if not isinstance(assessment, EventConsistency):
        raise ValidationExecutionError(
            "invalid event consistency policy result"
        )

    if assessment == EventConsistency.CONSISTENT:
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


# ---------------------------------------------------------------------
# V-11: 기타 Category 선택 근거 및 Category 불명확 판정
# ---------------------------------------------------------------------


class OtherCategoryEvidence(StrEnum):
    NO_SPECIFIC_CHILD_APPLIES = "NO_SPECIFIC_CHILD_APPLIES"
    SPECIFIC_CHILD_APPLIES = "SPECIFIC_CHILD_APPLIES"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True, slots=True)
class OtherCategorySelectionEvidence:
    """특정 후보 주제와 Root에 대한 '기타' 선택 근거."""

    normalized_title: str
    root_id: int
    conclusion: OtherCategoryEvidence



def resolve_other_category_ids(
    catalog: CategoryCatalog,
    root_id: int | None,
    evidence: OtherCategoryEvidence,
) -> tuple[int, ...] | None:
    """명확한 Root와 세부분류 배제 근거가 있을 때만 기타를 선택한다."""
    if not isinstance(evidence, OtherCategoryEvidence):
        raise ValidationExecutionError(
            "invalid other category evidence"
        )

    if (
        root_id is None
        or evidence is not OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES
    ):
        return None

    root = next(
        (
            item
            for item in catalog.roots
            if item.category_id == root_id
        ),
        None,
    )

    if root is None or not root.is_active:
        return None

    other_ids = tuple(
        child.category_id
        for child in catalog.children
        if child.parent_id == root_id
        and child.name == "기타"
    )

    if len(other_ids) > 1:
        raise ValidationExecutionError(
            "duplicate other category for root"
        )

    return catalog.select_active_child_ids(other_ids)


def has_valid_other_category_evidence(
    catalog: CategoryCatalog,
    category_ids: tuple[int, ...],
    normalized_title: str,
    other_category_evidence: tuple[
        OtherCategorySelectionEvidence, ...
    ],
) -> bool:
    """선택된 '기타' Child의 Root·주제·배제 근거를 검증한다."""
    evidence_by_root: dict[int, OtherCategoryEvidence] = {}

    for item in other_category_evidence:
        if (
            not isinstance(item, OtherCategorySelectionEvidence)
            or not isinstance(item.normalized_title, str)
            or type(item.root_id) is not int
            or not isinstance(item.conclusion, OtherCategoryEvidence)
        ):
            raise ValidationExecutionError(
                "invalid other category evidence"
            )

        if item.root_id in evidence_by_root:
            raise ValidationExecutionError(
                "duplicate other category evidence"
            )

        if item.normalized_title != normalized_title:
            return False

        evidence_by_root[item.root_id] = item.conclusion

    children_by_id = {
        child.category_id: child
        for child in catalog.children
    }

    for child_id in category_ids:
        child = children_by_id[child_id]

        if child.name != "기타":
            continue

        # '기타'와 동일 Root의 구체적인 Child를
        # 동시에 채택하는 모순을 허용하지 않는다.
        if any(
            other_id != child_id
            and children_by_id[other_id].parent_id == child.parent_id
            for other_id in category_ids
        ):
            return False

        conclusion = evidence_by_root.get(
            child.parent_id,
            OtherCategoryEvidence.UNDETERMINED,
        )

        resolved_ids = resolve_other_category_ids(
            catalog,
            root_id=child.parent_id,
            evidence=conclusion,
        )

        if resolved_ids != (child_id,):
            return False

    return True


def evaluate_category_unclear_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
    event_consistency: EventConsistency,
    catalog: CategoryCatalog,
    proposed_child_ids: tuple[int, ...] | None,
) -> CandidateEvaluation | None:
    """Source·사건이 확인됐지만 활성 Child가 불명확하면 보류한다."""
    if not screening.valid_sources:
        return None

    if not isinstance(event_consistency, EventConsistency):
        raise ValidationExecutionError(
            "invalid event consistency policy result"
        )

    if event_consistency is not EventConsistency.CONSISTENT:
        return None

    selected_ids = catalog.select_active_child_ids(
        proposed_child_ids or ()
    )

    if selected_ids is not None:
        # Category 검증 통과. 아직 WOULD_ACCEPT 판정은 아니다.
        return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        raise ValidationExecutionError(
            "eligible source exists with invalid candidate title"
        )

    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.CATEGORY_UNCLEAR,),
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )

# ---------------------------------------------------------------------
# V-16: 미확인·차단 도메인 혼합 및 전체 차단 판정
# ---------------------------------------------------------------------


_DOMAIN_RESTRICTION_ISSUES = frozenset({
    SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
    SourceIssueCode.BLOCKED_SOURCE_DOMAIN,
})


def evaluate_unknown_blocked_domain_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
) -> CandidateEvaluation | None:
    """미확인+차단 혼합 또는 전체 차단 Source를 판정한다."""
    if screening.valid_sources:
        return None

    if not candidate.source_candidates:
        return None

    # 모든 원본 Source가 각자의 Domain Issue로 설명되어야 한다.
    if len(screening.source_issues) != len(candidate.source_candidates):
        return None

    if tuple(
        issue.item_news_index
        for issue in screening.source_issues
    ) != tuple(
        source.item_news_index
        for source in candidate.source_candidates
    ):
        return None

    issue_codes = tuple(
        issue.code
        for issue in screening.source_issues
    )

    if any(
        code not in _DOMAIN_RESTRICTION_ISSUES
        for code in issue_codes
    ):
        return None

    has_unknown = (
        SourceIssueCode.UNKNOWN_SOURCE_DOMAIN in issue_codes
    )
    has_blocked = (
        SourceIssueCode.BLOCKED_SOURCE_DOMAIN in issue_codes
    )

    # 미확인 출처만 존재하는 경우는 V-04의 책임이다.
    if has_unknown and not has_blocked:
        return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        return None

    if has_unknown:
        decision = CandidateDecision.DEFERRED
        reason_codes = (
            ReasonCode.NO_ELIGIBLE_SOURCE,
            ReasonCode.UNKNOWN_SOURCE_DOMAIN,
        )
    else:
        # 여기서는 모든 Source가 명백한 차단 도메인이다.
        decision = CandidateDecision.SKIPPED
        reason_codes = (
            ReasonCode.BLOCKED_SOURCES_ONLY,
        )

    return CandidateEvaluation(
        decision=decision,
        reason_codes=reason_codes,
        normalized_title=title.normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=screening.source_issues,
    )


# ---------------------------------------------------------------------
# V-17: 사건 일관성 -> 활성 Child Category 판정 연결
# ---------------------------------------------------------------------


def evaluate_event_and_category_gates(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
    event_rules: EventConsistencyRules,
    catalog: CategoryCatalog,
    proposed_child_ids: tuple[int, ...] | None,
) -> CandidateEvaluation | None:
    """적합 Source가 있는 후보의 사건 및 Category 보류 검증을 연결한다."""

    # Source 부족은 앞선 Source 판정 단계의 책임이다.
    if not screening.valid_sources:
        return None

    # 1. 사건 일관성 검증
    event_result = evaluate_event_consistency_gate(
        candidate,
        screening,
        event_rules,
    )

    if event_result is not None:
        return event_result

    # 적합 Source가 존재하고 사건 Gate를 통과했으므로
    # 이 지점에서는 사건 일관성이 CONSISTENT이다.
    # 2. 활성 Child Category 검증
    return evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        catalog,
        proposed_child_ids,
    )



# ---------------------------------------------------------------------
# V-19: P3 최종 기술 판정
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# V-19: P3 최종 기술 판정
# ---------------------------------------------------------------------



def validate_p3_candidate(
    candidate: ParsedCandidate,
    *,
    topic_rules: TopicRules,
    domain_policy: DomainPolicy,
    relevance_rules: SourceRelevanceRules,
    event_rules: EventConsistencyRules,
    category_catalog: CategoryCatalog,
    proposed_child_ids: tuple[int, ...] | None,
    category_evidence_rules: CategoryEvidenceRules,
    article_scope_rules: ArticleTopicScopeRules,
    other_category_evidence: tuple[
        OtherCategorySelectionEvidence, ...
    ] = (),
) -> CandidateEvaluation:
    """합성 Fixture 기반 P3 최종 기술 판정. 외부 I/O 없음."""

    def second_stage(
        current: ParsedCandidate,
    ) -> CandidateEvaluation:
        title = normalize_title(current.raw_title)

        # ---------------------------------------------------------
        # R-03: 후보 제목 정규화 실패
        # ---------------------------------------------------------
        if title is None:
            # 외부 입력 데이터 품질 문제는 정책 실행 실패가 아니다.
            # 유효한 제목이 없으므로 후속 정책·Source를 검사하지 않는다.
            return CandidateEvaluation(
                decision=CandidateDecision.DEFERRED,
                reason_codes=(
                    ReasonCode.CANDIDATE_TITLE_INVALID,
                ),
                normalized_title=None,
                valid_sources=(),
                category_ids=(),
                warnings=current.warnings,
                source_issues=(),
            )

        # ---------------------------------------------------------
        # 1. Source별 필수 정보·도메인·관련성·중복 검증
        # ---------------------------------------------------------
        screening = screen_candidate_sources(
            current,
            domain_policy,
            relevance_rules,
        )

        # ---------------------------------------------------------
        # 2. 적합 Source가 없으면 Source 부족 판정 우선
        # ---------------------------------------------------------
        if not screening.valid_sources:
            source_gates = (
                evaluate_unknown_blocked_domain_gate,
                evaluate_unknown_domain_gate,
                evaluate_missing_or_invalid_source_gate,
                evaluate_relevance_unclear_gate,
            )

            for gate in source_gates:
                result = gate(current, screening)

                if result is not None:
                    return result

            source_indices = tuple(
                source.item_news_index
                for source in current.source_candidates
            )
            issue_indices = tuple(
                issue.item_news_index
                for issue in screening.source_issues
            )

            if source_indices != issue_indices:
                raise ValidationExecutionError(
                    "incomplete source screening result"
                )

            issue_codes = {
                issue.code
                for issue in screening.source_issues
            }

            reasons: list[ReasonCode] = [
                ReasonCode.NO_ELIGIBLE_SOURCE,
            ]

            if (
                SourceIssueCode.UNKNOWN_SOURCE_DOMAIN
                in issue_codes
            ):
                reasons.append(
                    ReasonCode.UNKNOWN_SOURCE_DOMAIN
                )

            if (
                SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR
                in issue_codes
            ):
                reasons.append(
                    ReasonCode.RELEVANCE_UNCLEAR
                )

            return CandidateEvaluation(
                decision=CandidateDecision.DEFERRED,
                reason_codes=tuple(reasons),
                normalized_title=title.normalized_title,
                valid_sources=(),
                category_ids=(),
                warnings=current.warnings,
                source_issues=screening.source_issues,
            )

        # ---------------------------------------------------------
        # 3. R-02B: 적합 기사 근거로 2차 주제 범위 확인
        # ---------------------------------------------------------
        article_scope_result = evaluate_article_topic_scope_gate(
            current,
            screening,
            article_scope_rules,
        )

        if article_scope_result is not None:
            return article_scope_result

        # ---------------------------------------------------------
        # 4. 사건 일관성 및 활성 Child 검증
        # ---------------------------------------------------------
        deferred_result = evaluate_event_and_category_gates(
            current,
            screening,
            event_rules,
            category_catalog,
            proposed_child_ids,
        )

        if deferred_result is not None:
            return deferred_result

        category_ids = category_catalog.select_active_child_ids(
            proposed_child_ids or ()
        )

        if category_ids is None:
            raise ValidationExecutionError(
                "category validation returned inconsistent result"
            )

        # ---------------------------------------------------------
        # 5. R-02A: 실제 후보·기사에 대한 Child 근거 확인
        # ---------------------------------------------------------
        supported_ids = category_evidence_rules.supported_child_ids(
            title.normalized_title,
            screening.valid_sources,
        )

        if supported_ids is not None:
            if (
                not isinstance(supported_ids, tuple)
                or any(
                    type(child_id) is not int
                    for child_id in supported_ids
                )
            ):
                raise ValidationExecutionError(
                    "invalid category evidence policy result"
                )

        verified_supported_ids = (
            category_catalog.select_active_child_ids(supported_ids)
            if supported_ids is not None
            else None
        )

        if supported_ids and verified_supported_ids is None:
            raise ValidationExecutionError(
                "category evidence references unavailable child"
            )

        category_supported = (
            verified_supported_ids is not None
            and set(category_ids).issubset(verified_supported_ids)
        )

        # ---------------------------------------------------------
        # 6. R-01: '기타' 선택 시 추가 배제 근거 확인
        # ---------------------------------------------------------
        other_supported = (
            category_supported
            and has_valid_other_category_evidence(
                catalog=category_catalog,
                category_ids=category_ids,
                normalized_title=title.normalized_title,
                other_category_evidence=other_category_evidence,
            )
        )

        if not other_supported:
            return CandidateEvaluation(
                decision=CandidateDecision.DEFERRED,
                reason_codes=(ReasonCode.CATEGORY_UNCLEAR,),
                normalized_title=title.normalized_title,
                valid_sources=(),
                category_ids=(),
                warnings=current.warnings,
                source_issues=screening.source_issues,
            )

        # ---------------------------------------------------------
        # 7. 모든 검증 통과: 기술적 채택 가능 판정
        # ---------------------------------------------------------
        return CandidateEvaluation(
            decision=CandidateDecision.WOULD_ACCEPT,
            reason_codes=(
                ReasonCode.VALIDATED_BY_FIXTURE_RULES,
            ),
            normalized_title=title.normalized_title,
            valid_sources=screening.valid_sources,
            category_ids=category_ids,
            warnings=current.warnings,
            source_issues=screening.source_issues,
        )

    return evaluate_candidate(
        candidate,
        topic_rules,
        second_stage,
    )

# ---------------------------------------------------------------------
# Final Review R-02B:
# 기사 근거를 이용한 2차 관심 범위 판정
# ---------------------------------------------------------------------




def evaluate_article_topic_scope_gate(
    candidate: ParsedCandidate,
    screening: SourceScreeningResult,
    article_scope_rules: ArticleTopicScopeRules,
) -> CandidateEvaluation | None:
    """적합 기사와 중복 기사의 명시적 범위 근거를 검증한다.

    Source 저장 후보는 기존 중복 제거 결과를 유지한다.
    None은 기존 Event·Category 검증을 계속한다는 의미다.
    """

    # 적합 Source가 없으면 기존 Source 부족 판정이 우선한다.
    if not screening.valid_sources:
        return None

    title = normalize_title(candidate.raw_title)

    if title is None:
        raise ValidationExecutionError(
            "eligible source exists with invalid candidate title"
        )

    # ---------------------------------------------------------
    # 1. 기존 적합 Source의 제목 수집
    # ---------------------------------------------------------
    article_titles: list[str] = [
        source.source_title
        for source in screening.valid_sources
    ]

    # ---------------------------------------------------------
    # 2. R-04B: 중복으로 제외된 기사 식별
    #
    # DUPLICATE_SOURCE는 Source Screening에서
    # 제목·URL·도메인·관련성 검사를 통과한 뒤 부여된다.
    #
    # 저장 대상에서는 제외하되, 범위 판단 근거에는 포함한다.
    # ---------------------------------------------------------
    duplicate_indices = {
        issue.item_news_index
        for issue in screening.source_issues
        if issue.code == SourceIssueCode.DUPLICATE_SOURCE
    }

    seen_duplicate_indices: set[int] = set()

    for source in candidate.source_candidates:
        if source.item_news_index not in duplicate_indices:
            continue

        if (
            source.item_news_index in seen_duplicate_indices
            or source.raw_title is None
        ):
            raise ValidationExecutionError(
                "invalid duplicate source screening result"
            )

        seen_duplicate_indices.add(
            source.item_news_index
        )

        article_titles.append(source.raw_title)

    if seen_duplicate_indices != duplicate_indices:
        raise ValidationExecutionError(
            "incomplete duplicate source screening result"
        )

    # ---------------------------------------------------------
    # 3. 모든 평가 대상의 명시적 Topic Scope 확인
    # ---------------------------------------------------------
    article_scopes: list[TopicScope] = []

    for raw_article_title in article_titles:
        normalized_article_title = normalize_title(
            raw_article_title
        )

        if normalized_article_title is None:
            raise ValidationExecutionError(
                "eligible source has invalid normalized title"
            )

        scope = article_scope_rules.classify(
            title.normalized_title,
            normalized_article_title.normalized_title,
        )

        if not isinstance(scope, TopicScope):
            raise ValidationExecutionError(
                "invalid article topic scope policy result"
            )

        article_scopes.append(scope)

    # ---------------------------------------------------------
    # 4. 모든 평가 대상이 명백히 범위 밖인 경우
    # ---------------------------------------------------------
    if all(
        scope == TopicScope.CLEAR_OUT_OF_SCOPE
        for scope in article_scopes
    ):
        return CandidateEvaluation(
            decision=CandidateDecision.SKIPPED,
            reason_codes=(ReasonCode.OUT_OF_SCOPE,),
            normalized_title=title.normalized_title,
            valid_sources=(),
            category_ids=(),
            warnings=candidate.warnings,
            source_issues=screening.source_issues,
        )

    # ---------------------------------------------------------
    # 5. R-04C: 관심 범위 불명확성과 사건 모호성 분리
    #
    # 일부 기사에서는 범위 밖 근거가 확인되었지만,
    # 다른 기사에서는 범위 밖이라는 사실이 확정되지 않았다.
    #
    # 이는 사건 충돌 자체가 아니므로
    # EVENT_AMBIGUOUS를 사용하지 않는다.
    # ---------------------------------------------------------
    if any(
        scope == TopicScope.CLEAR_OUT_OF_SCOPE
        for scope in article_scopes
    ):
        return CandidateEvaluation(
            decision=CandidateDecision.DEFERRED,
            reason_codes=(ReasonCode.TOPIC_SCOPE_UNCLEAR,),
            normalized_title=title.normalized_title,
            valid_sources=(),
            category_ids=(),
            warnings=candidate.warnings,
            source_issues=screening.source_issues,
        )

    # ---------------------------------------------------------
    # 6. 범위 밖 근거가 없으면 기존 Event·Category 검증 계속
    # ---------------------------------------------------------
    return None
