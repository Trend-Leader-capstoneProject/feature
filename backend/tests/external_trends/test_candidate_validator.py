
"""P3 V-01 — 명백한 범위 밖 검색어만 1차에서 제외한다."""

import ast
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from app.external_trends.candidate_validator import (
    CategoryCatalog,
    CategoryChild,
    CategoryRoot,
    DomainPolicy,
    EventConsistency,
    OtherCategoryEvidence,
    SourceRelevance,
    SourceScreeningResult,
    TopicScope,
    ValidationExecutionError,
    evaluate_candidate,
    evaluate_category_unclear_gate,
    evaluate_event_consistency_gate,
    evaluate_missing_or_invalid_source_gate,
    evaluate_relevance_unclear_gate,
    evaluate_topic_gate,
    evaluate_unknown_domain_gate,
    resolve_other_category_ids,
    screen_candidate_sources,
)
from app.external_trends.rss_parser import parse_rss_feed
from app.external_trends.types import (
    CandidateDecision,
    CandidateEvaluation,
    NormalizedSource,
    ParsedCandidate,
    ParsedSource,
    ReasonCode,
    SourceIssue,
    SourceIssueCode,
    WarningCode,
)


@dataclass(frozen=True)
class FixtureTopicRules:
    scopes: dict[str, TopicScope]

    def classify(self, normalized_title: str) -> TopicScope:
        return self.scopes.get(normalized_title, TopicScope.AMBIGUOUS)


def make_candidate(
    raw_title: str,
    *,
    warnings: tuple[WarningCode, ...] = (),
    sources: tuple[ParsedSource, ...] = (),
) -> ParsedCandidate:
    return ParsedCandidate(
        item_index=0,
        raw_title=raw_title,
        rss_published_at=None,
        source_candidates=sources,
        warnings=warnings,
    )


# ---------------------------------------------------------------------
# V-01: 명백한 범위 밖 검색어만 SKIPPED 처리
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_title", "normalized_title"),
    [
        ("  OUTSIDE   TOPIC ", "outside topic"),
        ("가상 제외 주제", "가상 제외 주제"),
    ],
)
def test_v01_explicit_out_of_scope_returns_skipped(
    raw_title: str,
    normalized_title: str,
) -> None:
    candidate = make_candidate(raw_title)
    rules = FixtureTopicRules({
        normalized_title: TopicScope.CLEAR_OUT_OF_SCOPE
    })

    assert evaluate_topic_gate(candidate, rules) == CandidateEvaluation(
        decision=CandidateDecision.SKIPPED,
        reason_codes=(ReasonCode.OUT_OF_SCOPE,),
        normalized_title=normalized_title,
        valid_sources=(),
        category_ids=(),
        warnings=(),
        source_issues=(),
    )


@pytest.mark.parametrize(
    "scope",
    [TopicScope.POSSIBLE_IN_SCOPE, TopicScope.AMBIGUOUS],
)
def test_v01_non_excluded_scope_proceeds_to_second_stage(
    scope: TopicScope,
) -> None:
    candidate = make_candidate("가상 검색어")
    rules = FixtureTopicRules({"가상 검색어": scope})

    assert evaluate_topic_gate(candidate, rules) is None


def test_v01_unregistered_title_is_not_skipped() -> None:
    candidate = make_candidate("사전에 없는 주제")
    rules = FixtureTopicRules({
        "다른 주제": TopicScope.CLEAR_OUT_OF_SCOPE
    })

    assert evaluate_topic_gate(candidate, rules) is None


def test_v01_no_substring_based_out_of_scope() -> None:
    candidate = make_candidate("가상 제외 주제 확장")
    rules = FixtureTopicRules({
        "가상 제외 주제": TopicScope.CLEAR_OUT_OF_SCOPE
    })

    assert evaluate_topic_gate(candidate, rules) is None


def test_v01_skip_preserves_warnings_and_does_not_evaluate_sources() -> None:
    candidate = make_candidate(
        "범위 밖 합성 검색어",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(ParsedSource(0, None, None, None),),
    )
    rules = FixtureTopicRules({
        "범위 밖 합성 검색어": TopicScope.CLEAR_OUT_OF_SCOPE
    })

    result = evaluate_topic_gate(candidate, rules)

    assert result is not None
    assert result.decision == CandidateDecision.SKIPPED
    assert result.reason_codes == (ReasonCode.OUT_OF_SCOPE,)
    assert result.warnings == (WarningCode.INVALID_PUB_DATE,)
    assert result.valid_sources == ()
    assert result.category_ids == ()
    assert result.source_issues == ()



# ---------------------------------------------------------------------
# V-02: 모호·미등록 검색어의 2차 검증 연결
# ---------------------------------------------------------------------


def _fake_second_stage(candidate: ParsedCandidate) -> CandidateEvaluation:
    """V-02 호출 검증용 대역. 실제 Source 검증은 수행하지 않는다."""
    return CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.NO_ELIGIBLE_SOURCE,),
        normalized_title=None,
        valid_sources=(),
        category_ids=(),
        warnings=candidate.warnings,
        source_issues=(),
    )


@pytest.mark.parametrize(
    ("raw_title", "scope_by_title"),
    [
        (
            "사전에 없는 합성 주제",
            {"다른 주제": TopicScope.CLEAR_OUT_OF_SCOPE},
        ),
        (
            "중의적인 가상 검색어",
            {"중의적인 가상 검색어": TopicScope.AMBIGUOUS},
        ),
        (
            "관심 범위 가능 주제",
            {"관심 범위 가능 주제": TopicScope.POSSIBLE_IN_SCOPE},
        ),
    ],
    ids=["unregistered", "ambiguous", "possible-in-scope"],
)
def test_v02_non_excluded_candidate_reaches_second_stage(
    raw_title: str,
    scope_by_title: dict[str, TopicScope],
) -> None:
    candidate = make_candidate(raw_title)
    rules = FixtureTopicRules(scope_by_title)
    received: list[ParsedCandidate] = []

    def spy_second_stage(
        received_candidate: ParsedCandidate,
    ) -> CandidateEvaluation:
        received.append(received_candidate)
        return _fake_second_stage(received_candidate)

    result = evaluate_candidate(
        candidate,
        rules,
        spy_second_stage,
    )

    assert received == [candidate]
    assert received[0] is candidate
    assert result == _fake_second_stage(candidate)


def test_v02_skipped_candidate_does_not_reach_second_stage() -> None:
    candidate = make_candidate("명백한 제외 주제")
    rules = FixtureTopicRules({
        "명백한 제외 주제": TopicScope.CLEAR_OUT_OF_SCOPE
    })

    def forbidden_second_stage(
        received_candidate: ParsedCandidate,
    ) -> CandidateEvaluation:
        pytest.fail("SKIPPED 후보는 2차 검증을 호출하면 안 됩니다.")

    result = evaluate_candidate(
        candidate,
        rules,
        forbidden_second_stage,
    )

    assert result.decision == CandidateDecision.SKIPPED
    assert result.reason_codes == (ReasonCode.OUT_OF_SCOPE,)
    assert result.valid_sources == ()
    assert result.category_ids == ()


def test_v02_preserves_candidate_data_during_handoff() -> None:
    source = ParsedSource(
        item_news_index=0,
        raw_title="가상 기사",
        raw_url="https://news.example.test/article",
        publisher_name="가상 언론",
    )
    candidate = make_candidate(
        "미등록 검색어",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(source,),
    )
    rules = FixtureTopicRules({})
    received: list[ParsedCandidate] = []

    def spy_second_stage(
        received_candidate: ParsedCandidate,
    ) -> CandidateEvaluation:
        received.append(received_candidate)
        return _fake_second_stage(received_candidate)

    evaluate_candidate(candidate, rules, spy_second_stage)

    assert len(received) == 1
    assert received[0] is candidate
    assert received[0].source_candidates == (source,)
    assert received[0].warnings == (WarningCode.INVALID_PUB_DATE,)



# ---------------------------------------------------------------------
# V-03: 유효 Source 유지 및 부적합 Source별 사유 기록
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureSourceRelevanceRules:
    related: frozenset[tuple[str, str]] = frozenset()
    unrelated: frozenset[tuple[str, str]] = frozenset()

    def classify(
        self,
        normalized_topic: str,
        normalized_source_title: str,
    ) -> SourceRelevance:
        pair = (normalized_topic, normalized_source_title)

        if pair in self.related:
            return SourceRelevance.RELATED
        if pair in self.unrelated:
            return SourceRelevance.UNRELATED

        return SourceRelevance.UNCLEAR


def test_v03_keeps_one_valid_source_with_two_invalid_ones() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0,
                " 가상   콘서트 개막 ",
                "HTTPS://NEWS.Example.TEST:443/a?id=1&utm_source=rss",
                "가상 뉴스",
            ),
            ParsedSource(
                1, None, "https://news.example.test/b", "가상 뉴스"
            ),
            ParsedSource(
                2, "가상 콘서트 소식", "javascript:alert(1)", None
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 콘서트", "가상 콘서트 개막"),
        }),
    )

    result = screen_candidate_sources(candidate, policy, rules)
    canonical_url = "https://news.example.test/a?id=1"

    assert result.valid_sources == (
        NormalizedSource(
            source_title="가상 콘서트 개막",
            canonical_url=canonical_url,
            source_key=sha256(
                canonical_url.encode("utf-8")
            ).hexdigest(),
            publisher_name="가상 뉴스",
        ),
    )
    assert result.source_issues == (
        SourceIssue(1, SourceIssueCode.SOURCE_TITLE_MISSING),
        SourceIssue(2, SourceIssueCode.SOURCE_URL_INVALID),
    )


def test_v03_publisher_name_cannot_approve_unknown_hostname() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0,
                "가상 콘서트 개막",
                "https://news.example.test.attacker.test/a",
                "news.example.test",
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 콘서트", "가상 콘서트 개막"),
        }),
    )

    result = screen_candidate_sources(candidate, policy, rules)

    assert result.valid_sources == ()
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )


def test_v03_excludes_blocked_and_unrelated_sources() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0,
                "가상 콘서트 개막",
                "https://blocked.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "다른 분야 소식",
                "https://news.example.test/b",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset({"blocked.example.test"}),
    )
    rules = FixtureSourceRelevanceRules(
        unrelated=frozenset({
            ("가상 콘서트", "다른 분야 소식"),
        }),
    )

    result = screen_candidate_sources(candidate, policy, rules)

    assert result.valid_sources == ()
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
        SourceIssue(1, SourceIssueCode.SOURCE_UNRELATED),
    )


def test_v03_keeps_valid_source_order() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0, "첫 번째 기사", "https://news.example.test/a", "신문 A"
            ),
            ParsedSource(
                1, "두 번째 기사", "https://news.example.test/b", "신문 B"
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 콘서트", "첫 번째 기사"),
            ("가상 콘서트", "두 번째 기사"),
        }),
    )

    result = screen_candidate_sources(candidate, policy, rules)

    assert [s.canonical_url for s in result.valid_sources] == [
        "https://news.example.test/a",
        "https://news.example.test/b",
    ]
    assert result.source_issues == ()


def test_v03_unclear_relevance_is_not_called_unrelated() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0,
                "가상 콘서트 기사",
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset(),
    )

    result = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )

    assert result.valid_sources == ()
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
    )


def test_v03_invalid_source_title_is_not_eligible() -> None:
    candidate = make_candidate(
        "가상 콘서트",
        sources=(
            ParsedSource(
                0,
                "A" * 256,
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        frozenset({"news.example.test"}),
        frozenset(),
    )

    result = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )

    assert result.valid_sources == ()
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.SOURCE_TITLE_INVALID),
    )



# ---------------------------------------------------------------------
# V-04: 미확인 도메인만 존재할 경우 DEFERRED
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://unreviewed.example.test/a",
        "https://K.example.test/a",
    ],
)
def test_v04_unknown_only_returns_deferred(raw_url: str) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                raw_url,
                "news.example.test",
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({
            "news.example.test",
            "k.example.test",
        }),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules()

    screening = screen_candidate_sources(candidate, policy, rules)
    result = evaluate_unknown_domain_gate(candidate, screening)

    assert screening.valid_sources == ()
    assert screening.source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )
    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(
            ReasonCode.NO_ELIGIBLE_SOURCE,
            ReasonCode.UNKNOWN_SOURCE_DOMAIN,
        ),
        normalized_title="가상 행사",
        valid_sources=(),
        category_ids=(),
        warnings=(),
        source_issues=screening.source_issues,
    )


def test_v04_preserves_unknown_source_order_and_warnings() -> None:
    candidate = make_candidate(
        "가상 행사",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(
            ParsedSource(
                0,
                "첫 번째 기사",
                "https://unknown-one.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "두 번째 기사",
                "https://unknown-two.example.test/b",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset(),
        blocked_hosts=frozenset(),
    )

    screening = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )
    result = evaluate_unknown_domain_gate(candidate, screening)

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
        ReasonCode.UNKNOWN_SOURCE_DOMAIN,
    )
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )
    assert result.warnings == (WarningCode.INVALID_PUB_DATE,)
    assert result.valid_sources == ()
    assert result.category_ids == ()


def test_v04_connects_to_existing_topic_gate() -> None:
    candidate = make_candidate(
        "미등록 가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://unknown.example.test/a",
                None,
            ),
        ),
    )
    topic_rules = FixtureTopicRules({})
    policy = DomainPolicy(
        approved_hosts=frozenset(),
        blocked_hosts=frozenset(),
    )
    received: list[ParsedCandidate] = []

    def second_stage(
        current: ParsedCandidate,
    ) -> CandidateEvaluation:
        received.append(current)

        screening = screen_candidate_sources(
            current, policy, FixtureSourceRelevanceRules()
        )
        result = evaluate_unknown_domain_gate(current, screening)

        assert result is not None
        return result

    result = evaluate_candidate(
        candidate,
        topic_rules,
        second_stage,
    )

    assert received == [candidate]
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
        ReasonCode.UNKNOWN_SOURCE_DOMAIN,
    )
    assert result.valid_sources == ()
    assert result.category_ids == ()


@pytest.mark.parametrize(
    ("raw_urls", "approved_hosts", "blocked_hosts"),
    [
        (
            (),
            frozenset(),
            frozenset(),
        ),
        (
            ("https://blocked.example.test/a",),
            frozenset(),
            frozenset({"blocked.example.test"}),
        ),
        (
            (
                "https://unknown.example.test/a",
                "https://blocked.example.test/b",
            ),
            frozenset(),
            frozenset({"blocked.example.test"}),
        ),
        (
            ("https://news.example.test/a",),
            frozenset({"news.example.test"}),
            frozenset(),
        ),
        (
            ("javascript:alert(1)",),
            frozenset(),
            frozenset(),
        ),
    ],
    ids=[
        "no-sources-v05",
        "blocked-only",
        "mixed-unknown-blocked-v16",
        "approved-source",
        "invalid-url-v05",
    ],
)
def test_v04_does_not_decide_other_source_cases(
    raw_urls: tuple[str, ...],
    approved_hosts: frozenset[str],
    blocked_hosts: frozenset[str],
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=tuple(
            ParsedSource(
                item_news_index=index,
                raw_title="가상 행사 기사",
                raw_url=url,
                publisher_name=None,
            )
            for index, url in enumerate(raw_urls)
        ),
    )
    policy = DomainPolicy(
        approved_hosts=approved_hosts,
        blocked_hosts=blocked_hosts,
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    assert evaluate_unknown_domain_gate(candidate, screening) is None



# ---------------------------------------------------------------------
# V-05: Source 부재·제목/URL 오류는 NO_ELIGIBLE_SOURCE
# ---------------------------------------------------------------------


def test_v05_no_sources_returns_deferred_before_category() -> None:
    candidate = make_candidate(
        "  가상   행사  ",
        warnings=(WarningCode.INVALID_PUB_DATE,),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset(),
        blocked_hosts=frozenset(),
    )

    screening = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )
    result = evaluate_missing_or_invalid_source_gate(
        candidate, screening
    )

    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.NO_ELIGIBLE_SOURCE,),
        normalized_title="가상 행사",
        valid_sources=(),
        category_ids=(),
        warnings=(WarningCode.INVALID_PUB_DATE,),
        source_issues=(),
    )


@pytest.mark.parametrize(
    ("raw_title", "raw_url", "expected_issue"),
    [
        (
            None,
            "https://news.example.test/a",
            SourceIssueCode.SOURCE_TITLE_MISSING,
        ),
        (
            "A" * 256,
            "https://news.example.test/a",
            SourceIssueCode.SOURCE_TITLE_INVALID,
        ),
        (
            "가상 행사 기사",
            None,
            SourceIssueCode.SOURCE_URL_INVALID,
        ),
        (
            "가상 행사 기사",
            "javascript:alert(1)",
            SourceIssueCode.SOURCE_URL_INVALID,
        ),
    ],
)
def test_v05_invalid_metadata_only_returns_deferred(
    raw_title: str | None,
    raw_url: str | None,
    expected_issue: SourceIssueCode,
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(ParsedSource(0, raw_title, raw_url, None),),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )

    screening = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )
    result = evaluate_missing_or_invalid_source_gate(
        candidate, screening
    )

    assert screening.valid_sources == ()
    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
    )
    assert result.source_issues == (
        SourceIssue(0, expected_issue),
    )
    assert result.valid_sources == ()
    assert result.category_ids == ()


def test_v05_preserves_multiple_source_issues_and_order() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0, None, "https://news.example.test/a", None
            ),
            ParsedSource(
                1, "가상 행사 기사", "file:///tmp/article", None
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )

    screening = screen_candidate_sources(
        candidate, policy, FixtureSourceRelevanceRules()
    )
    result = evaluate_missing_or_invalid_source_gate(
        candidate, screening
    )

    assert result is not None
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
    )
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.SOURCE_TITLE_MISSING),
        SourceIssue(1, SourceIssueCode.SOURCE_URL_INVALID),
    )
    assert result.valid_sources == ()
    assert result.category_ids == ()


@pytest.mark.parametrize(
    "issue_code",
    [
        SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
        SourceIssueCode.BLOCKED_SOURCE_DOMAIN,
        SourceIssueCode.SOURCE_UNRELATED,
        SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR,
    ],
)
def test_v05_does_not_take_over_other_policy_cases(
    issue_code: SourceIssueCode,
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(SourceIssue(0, issue_code),),
    )

    assert (
        evaluate_missing_or_invalid_source_gate(
            candidate, screening
        )
        is None
    )


def test_v05_does_not_decide_mixed_unknown_and_invalid() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(0, None, None, None),
            ParsedSource(1, "가상 행사 기사", None, None),
        ),
    )
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(
            SourceIssue(0, SourceIssueCode.SOURCE_TITLE_MISSING),
            SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        ),
    )

    assert (
        evaluate_missing_or_invalid_source_gate(
            candidate, screening
        )
        is None
    )


def test_v05_does_not_defer_when_eligible_source_exists() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )

    screening = screen_candidate_sources(
        candidate, policy, rules
    )

    assert len(screening.valid_sources) == 1
    assert (
        evaluate_missing_or_invalid_source_gate(
            candidate, screening
        )
        is None
    )



# ---------------------------------------------------------------------
# V-06: 활성 Child ID 검증·중복 제거·오름차순 정렬
# ---------------------------------------------------------------------


def make_v06_catalog() -> CategoryCatalog:
    """Frozen 분류명을 사용한 합성 카탈로그. ID는 테스트 전용이다."""
    return CategoryCatalog(
        roots=(
            CategoryRoot(10, "ENTERTAINMENT", True),
            CategoryRoot(20, "IT_DIGITAL", True),
            CategoryRoot(30, "FASHION", False),
        ),
        children=(
            CategoryChild(101, 10, "음악", True),
            CategoryChild(102, 10, "영화", True),
            CategoryChild(201, 20, "인공지능", True),
            CategoryChild(202, 20, "소프트웨어·앱", False),
            CategoryChild(301, 30, "의류", True),
        ),
    )


def test_v06_selects_single_active_child() -> None:
    catalog = make_v06_catalog()

    assert catalog.select_active_child_ids((101,)) == (101,)


def test_v06_sorts_and_deduplicates_multiple_children() -> None:
    catalog = make_v06_catalog()

    assert catalog.select_active_child_ids(
        (201, 101, 201, 102)
    ) == (101, 102, 201)


@pytest.mark.parametrize(
    "evidence_child_ids",
    [
        pytest.param((), id="no-evidence"),
        pytest.param((10,), id="root-id-directly"),
        pytest.param((999,), id="unknown-child"),
        pytest.param((202,), id="inactive-child"),
        pytest.param((301,), id="inactive-parent-root"),
    ],
)
def test_v06_does_not_select_unavailable_children(
    evidence_child_ids: tuple[int, ...],
) -> None:
    catalog = make_v06_catalog()

    assert catalog.select_active_child_ids(evidence_child_ids) is None


@pytest.mark.parametrize(
    ("roots", "children"),
    [
        pytest.param(
            (
                CategoryRoot(10, "ENTERTAINMENT", True),
                CategoryRoot(10, "IT_DIGITAL", True),
            ),
            (),
            id="duplicate-root-id",
        ),
        pytest.param(
            (
                CategoryRoot(10, "ENTERTAINMENT", True),
                CategoryRoot(20, "ENTERTAINMENT", True),
            ),
            (),
            id="duplicate-root-code",
        ),
        pytest.param(
            (CategoryRoot(10, "ENTERTAINMENT", True),),
            (
                CategoryChild(101, 10, "음악", True),
                CategoryChild(101, 10, "영화", True),
            ),
            id="duplicate-child-id",
        ),
        pytest.param(
            (CategoryRoot(10, "ENTERTAINMENT", True),),
            (CategoryChild(10, 10, "음악", True),),
            id="root-child-id-collision",
        ),
        pytest.param(
            (CategoryRoot(10, "ENTERTAINMENT", True),),
            (CategoryChild(101, 999, "음악", True),),
            id="missing-parent-root",
        ),
    ],
)
def test_v06_invalid_catalog_is_execution_error(
    roots: tuple[CategoryRoot, ...],
    children: tuple[CategoryChild, ...],
) -> None:
    """오염된 정책 데이터는 정상 DEFERRED 판정으로 바꾸지 않는다."""
    with pytest.raises(ValidationExecutionError):
        CategoryCatalog(roots=roots, children=children)



# ---------------------------------------------------------------------
# V-07: 서로 다른 사건 및 사건 근거 부족에 따른 DEFERRED
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureEventRules:
    """합성 기사 제목에 명시적으로 부여한 사건 ID만 사용한다."""

    event_by_title: dict[str, str]

    def assess(
        self,
        candidate: ParsedCandidate,
        screening: SourceScreeningResult,
    ) -> EventConsistency:
        event_ids: list[str] = []

        for source in candidate.source_candidates:
            event_id = self.event_by_title.get(source.raw_title or "")

            if event_id is None:
                return EventConsistency.UNDETERMINED

            event_ids.append(event_id)

        if not event_ids:
            return EventConsistency.UNDETERMINED

        if len(set(event_ids)) > 1:
            return EventConsistency.AMBIGUOUS

        return EventConsistency.CONSISTENT


def make_v07_candidate(
    second_domain: str,
    *,
    warnings: tuple[WarningCode, ...] = (),
) -> ParsedCandidate:
    return make_candidate(
        "가상 축제",
        warnings=warnings,
        sources=(
            ParsedSource(
                0,
                "가상 축제 A 개막",
                "https://news.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "가상 축제 B 일정",
                f"https://{second_domain}/b",
                None,
            ),
        ),
    )


def screen_v07_candidate(
    candidate: ParsedCandidate,
) -> SourceScreeningResult:
    return screen_candidate_sources(
        candidate,
        DomainPolicy(
            approved_hosts=frozenset({"news.example.test"}),
            blocked_hosts=frozenset(),
        ),
        FixtureSourceRelevanceRules(
            related=frozenset({
                ("가상 축제", "가상 축제 a 개막"),
                ("가상 축제", "가상 축제 b 일정"),
            }),
        ),
    )


@pytest.mark.parametrize(
    "second_domain",
    [
        "news.example.test",
        "unknown.example.test",
    ],
)
def test_v07_different_events_are_deferred(
    second_domain: str,
) -> None:
    candidate = make_v07_candidate(
        second_domain,
        warnings=(WarningCode.INVALID_PUB_DATE,),
    )
    screening = screen_v07_candidate(candidate)

    rules = FixtureEventRules({
        "가상 축제 A 개막": "event-a",
        "가상 축제 B 일정": "event-b",
    })

    result = evaluate_event_consistency_gate(
        candidate, screening, rules
    )

    assert len(screening.valid_sources) >= 1
    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.EVENT_AMBIGUOUS,),
        normalized_title="가상 축제",
        valid_sources=(),
        category_ids=(),
        warnings=(WarningCode.INVALID_PUB_DATE,),
        source_issues=screening.source_issues,
    )


@pytest.mark.parametrize(
    "second_domain",
    [
        "news.example.test",
        "unknown.example.test",
    ],
)
def test_v07_confirmed_same_event_proceeds(
    second_domain: str,
) -> None:
    candidate = make_v07_candidate(second_domain)
    screening = screen_v07_candidate(candidate)

    expected_count = (
        2 if second_domain == "news.example.test" else 1
    )
    assert len(screening.valid_sources) == expected_count

    rules = FixtureEventRules({
        "가상 축제 A 개막": "event-a",
        "가상 축제 B 일정": "event-a",
    })

    assert (
        evaluate_event_consistency_gate(
            candidate, screening, rules
        )
        is None
    )


def test_v07_insufficient_event_evidence_is_deferred() -> None:
    candidate = make_v07_candidate("news.example.test")
    screening = screen_v07_candidate(candidate)

    # 두 번째 기사에 대한 사건 근거는 제공되지 않았다.
    rules = FixtureEventRules({
        "가상 축제 A 개막": "event-a",
    })

    result = evaluate_event_consistency_gate(
        candidate, screening, rules
    )

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (
        ReasonCode.EVENT_AMBIGUOUS,
    )
    assert result.valid_sources == ()
    assert result.category_ids == ()


@pytest.mark.parametrize(
    "sources",
    [
        (),
        (
            ParsedSource(
                0,
                "가상 축제 A 개막",
                "https://unknown.example.test/a",
                None,
            ),
        ),
    ],
)
def test_v07_does_not_override_source_shortage(
    sources: tuple[ParsedSource, ...],
) -> None:
    candidate = make_candidate("가상 축제", sources=sources)
    screening = screen_v07_candidate(candidate)

    class ForbiddenEventRules:
        def assess(
            self,
            candidate: ParsedCandidate,
            screening: SourceScreeningResult,
        ) -> EventConsistency:
            pytest.fail("유효 Source가 없으면 사건 판정을 호출하지 않습니다.")

    assert screening.valid_sources == ()
    assert (
        evaluate_event_consistency_gate(
            candidate, screening, ForbiddenEventRules()
        )
        is None
    )


def test_v07_policy_receives_candidate_and_screening() -> None:
    candidate = make_v07_candidate("unknown.example.test")
    screening = screen_v07_candidate(candidate)
    received: list[
        tuple[ParsedCandidate, SourceScreeningResult]
    ] = []

    class SpyEventRules:
        def assess(
            self,
            candidate: ParsedCandidate,
            screening: SourceScreeningResult,
        ) -> EventConsistency:
            received.append((candidate, screening))
            return EventConsistency.AMBIGUOUS

    result = evaluate_event_consistency_gate(
        candidate, screening, SpyEventRules()
    )

    assert len(received) == 1
    assert received[0][0] is candidate
    assert received[0][1] is screening
    assert result is not None
    assert result.source_issues == screening.source_issues



# ---------------------------------------------------------------------
# V-08: 미등록 검색어와 관련성 근거 부족의 보류 판정
# ---------------------------------------------------------------------


def screen_v08_candidate(
    candidate: ParsedCandidate,
    rules: FixtureSourceRelevanceRules | None = None,
) -> SourceScreeningResult:
    """V-08 합성 Fixture의 Source Screening을 수행한다."""
    return screen_candidate_sources(
        candidate,
        DomainPolicy(
            approved_hosts=frozenset({"news.example.test"}),
            blocked_hosts=frozenset(),
        ),
        rules if rules is not None else FixtureSourceRelevanceRules(),
    )


def test_v08_unregistered_topic_reaches_deferred_decision() -> None:
    candidate = make_candidate(
        "가상 AI 행사",
        sources=(
            ParsedSource(
                0,
                "가상 AI 행사 발표",
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    received: list[ParsedCandidate] = []

    def second_stage(
        current: ParsedCandidate,
    ) -> CandidateEvaluation:
        received.append(current)
        screening = screen_v08_candidate(current)

        assert screening.source_issues == (
            SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
        )

        result = evaluate_relevance_unclear_gate(current, screening)
        assert result is not None
        return result

    # 미등록 검색어는 기본적으로 AMBIGUOUS이며 조기 제외하지 않는다.
    result = evaluate_candidate(
        candidate,
        FixtureTopicRules({}),
        second_stage,
    )

    assert received == [candidate]
    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(
            ReasonCode.NO_ELIGIBLE_SOURCE,
            ReasonCode.RELEVANCE_UNCLEAR,
        ),
        normalized_title="가상 ai 행사",
        valid_sources=(),
        category_ids=(),
        warnings=(),
        source_issues=(
            SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
        ),
    )


@pytest.mark.parametrize(
    ("topic", "article"),
    [
        ("가상 게임", "가상 게임 업데이트"),
        ("AI 행사", "AI 행사 일정"),
    ],
)
def test_v08_substring_does_not_prove_relevance(
    topic: str,
    article: str,
) -> None:
    candidate = make_candidate(
        topic,
        sources=(
            ParsedSource(
                0,
                article,
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    screening = screen_v08_candidate(candidate)

    assert screening.valid_sources == ()
    assert screening.source_issues == (
        SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
    )

    result = evaluate_relevance_unclear_gate(candidate, screening)

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
        ReasonCode.RELEVANCE_UNCLEAR,
    )


def test_v08_preserves_multiple_source_issues_and_warnings() -> None:
    candidate = make_candidate(
        "가상 행사",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(
            ParsedSource(
                0,
                "첫 번째 가상 행사 기사",
                "https://news.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "두 번째 가상 행사 기사",
                "https://news.example.test/b",
                None,
            ),
        ),
    )
    screening = screen_v08_candidate(candidate)

    result = evaluate_relevance_unclear_gate(candidate, screening)

    assert result is not None
    assert result.reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
        ReasonCode.RELEVANCE_UNCLEAR,
    )
    assert result.source_issues == (
        SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
        SourceIssue(1, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
    )
    assert result.warnings == (WarningCode.INVALID_PUB_DATE,)
    assert result.valid_sources == ()
    assert result.category_ids == ()


def test_v08_explicitly_related_source_proceeds() -> None:
    candidate = make_candidate(
        "가상 AI 행사",
        sources=(
            ParsedSource(
                0,
                "가상 AI 행사 발표",
                "https://news.example.test/a",
                None,
            ),
        ),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 ai 행사", "가상 ai 행사 발표"),
        }),
    )
    screening = screen_v08_candidate(candidate, rules)

    assert len(screening.valid_sources) == 1
    assert screening.source_issues == ()
    assert evaluate_relevance_unclear_gate(candidate, screening) is None


def test_v08_no_sources_remains_v05_responsibility() -> None:
    candidate = make_candidate("가상 행사")
    screening = screen_v08_candidate(candidate)

    assert screening.valid_sources == ()
    assert screening.source_issues == ()
    assert evaluate_relevance_unclear_gate(candidate, screening) is None


@pytest.mark.parametrize(
    "issue_code",
    [
        SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
        SourceIssueCode.BLOCKED_SOURCE_DOMAIN,
        SourceIssueCode.SOURCE_TITLE_MISSING,
        SourceIssueCode.SOURCE_UNRELATED,
    ],
)
def test_v08_does_not_take_over_other_issue_codes(
    issue_code: SourceIssueCode,
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(ParsedSource(0, "가상 행사 기사", None, None),),
    )
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(SourceIssue(0, issue_code),),
    )

    assert evaluate_relevance_unclear_gate(candidate, screening) is None


def test_v08_mixed_issues_require_later_combined_decision() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(0, "첫 번째 기사", None, None),
            ParsedSource(1, "두 번째 기사", None, None),
        ),
    )
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(
            SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
            SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        ),
    )

    assert evaluate_relevance_unclear_gate(candidate, screening) is None


def test_v08_incomplete_screening_does_not_decide() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(0, "첫 번째 기사", None, None),
            ParsedSource(1, "두 번째 기사", None, None),
        ),
    )
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(
            SourceIssue(0, SourceIssueCode.SOURCE_RELEVANCE_UNCLEAR),
        ),
    )

    assert evaluate_relevance_unclear_gate(candidate, screening) is None



# ---------------------------------------------------------------------
# V-09: 승인·미확인·차단 도메인 혼합 Source 선별
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hosts", "expected_valid_indices", "expected_issues"),
    [
        pytest.param(
            (
                "news.example.test",
                "unknown.example.test",
                "blocked.example.test",
            ),
            (0,),
            (
                (1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
                (2, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
            ),
            id="approved-first",
        ),
        pytest.param(
            (
                "unknown.example.test",
                "blocked.example.test",
                "news.example.test",
            ),
            (2,),
            (
                (0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
                (1, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
            ),
            id="approved-last",
        ),
        pytest.param(
            (
                "news.example.test",
                "unknown.example.test",
                "news.example.test",
                "blocked.example.test",
            ),
            (0, 2),
            (
                (1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
                (3, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
            ),
            id="multiple-approved",
        ),
    ],
)
def test_v09_mixed_domains_keep_approved_related_sources_only(
    hosts: tuple[str, ...],
    expected_valid_indices: tuple[int, ...],
    expected_issues: tuple[tuple[int, SourceIssueCode], ...],
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=tuple(
            ParsedSource(
                item_news_index=index,
                raw_title=f"가상 행사 기사 {index}",
                raw_url=(
                    f"https://{hostname}/article/{index}"
                    f"?utm_source=rss&id={index}"
                ),
                publisher_name="news.example.test",
            )
            for index, hostname in enumerate(hosts)
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset({"blocked.example.test"}),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset(
            ("가상 행사", f"가상 행사 기사 {index}")
            for index in range(len(hosts))
        ),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    expected_urls = tuple(
        f"https://news.example.test/article/{index}?id={index}"
        for index in expected_valid_indices
    )

    assert tuple(
        source.canonical_url
        for source in screening.valid_sources
    ) == expected_urls

    assert tuple(
        source.source_title
        for source in screening.valid_sources
    ) == tuple(
        f"가상 행사 기사 {index}"
        for index in expected_valid_indices
    )

    assert tuple(
        source.source_key
        for source in screening.valid_sources
    ) == tuple(
        sha256(url.encode("utf-8")).hexdigest()
        for url in expected_urls
    )

    assert tuple(
        (issue.item_news_index, issue.code)
        for issue in screening.source_issues
    ) == expected_issues


def test_v09_mixed_domains_do_not_defer_eligible_sources_early() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 개막",
                "https://news.example.test/a",
                "가상 뉴스",
            ),
            ParsedSource(
                1,
                "가상 행사 소식",
                "https://unknown.example.test/b",
                "news.example.test",
            ),
            ParsedSource(
                2,
                "가상 행사 안내",
                "https://blocked.example.test/c",
                "가상 뉴스",
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset({"blocked.example.test"}),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 개막"),
            ("가상 행사", "가상 행사 소식"),
            ("가상 행사", "가상 행사 안내"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    assert len(screening.valid_sources) == 1
    assert screening.valid_sources[0].canonical_url == (
        "https://news.example.test/a"
    )
    assert screening.source_issues == (
        SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        SourceIssue(2, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
    )

    # 적합 Source가 있으므로 Source 부족 게이트가
    # 후보 전체를 조기 보류해서는 안 된다.
    assert evaluate_unknown_domain_gate(candidate, screening) is None
    assert (
        evaluate_missing_or_invalid_source_gate(candidate, screening)
        is None
    )
    assert evaluate_relevance_unclear_gate(candidate, screening) is None



# ---------------------------------------------------------------------
# V-10: 가짜 서브도메인·접두어·사용자 정보 기반 도메인 사칭
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_url", "expected_issue"),
    [
        pytest.param(
            "https://news.example.test.attacker.test/a",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="approved-host-as-prefix",
        ),
        pytest.param(
            "https://news.example.test.evil.test/a",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="approved-host-with-extra-suffix",
        ),
        pytest.param(
            "https://fake-news.example.test/a",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="fake-subdomain",
        ),
        pytest.param(
            "https://news.example.test-fake/a",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="fake-host-suffix",
        ),
        pytest.param(
            "https://attacker.test/news.example.test/a",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="approved-host-in-path",
        ),
        pytest.param(
            "https://attacker.test/a?host=news.example.test",
            SourceIssueCode.UNKNOWN_SOURCE_DOMAIN,
            id="approved-host-in-query",
        ),
        pytest.param(
            "https://news.example.test@attacker.test/a",
            SourceIssueCode.SOURCE_URL_INVALID,
            id="userinfo-host-spoofing",
        ),
        pytest.param(
            "https://user@news.example.test/a",
            SourceIssueCode.SOURCE_URL_INVALID,
            id="userinfo-on-approved-host",
        ),
        pytest.param(
            "https://news.example.test./a",
            SourceIssueCode.SOURCE_URL_INVALID,
            id="trailing-host-dot",
        ),
        pytest.param(
            "https://news%2eexample.test/a",
            SourceIssueCode.SOURCE_URL_INVALID,
            id="encoded-host-dot",
        ),
    ],
)
def test_v10_spoofed_hosts_are_never_approved(
    raw_url: str,
    expected_issue: SourceIssueCode,
) -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                raw_url,
                "news.example.test",
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    assert screening.valid_sources == ()
    assert screening.source_issues == (
        SourceIssue(0, expected_issue),
    )


def test_v10_real_approved_hostname_is_still_accepted() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                (
                    "HTTPS://NEWS.Example.TEST:443/a"
                    "?id=42&utm_source=rss"
                ),
                "가상 뉴스",
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    expected_url = "https://news.example.test/a?id=42"

    assert len(screening.valid_sources) == 1
    assert screening.valid_sources[0].canonical_url == expected_url
    assert screening.valid_sources[0].source_key == (
        sha256(expected_url.encode("utf-8")).hexdigest()
    )
    assert screening.source_issues == ()


def test_v10_unicode_hostname_is_not_ascii_approved_host() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://K.example.test/a",
                "가상 뉴스",
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"k.example.test"}),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    assert screening.valid_sources == ()
    assert screening.source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )


def test_v10_spoofed_source_does_not_remove_valid_source() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://news.example.test.attacker.test/a",
                None,
            ),
            ParsedSource(
                1,
                "가상 행사 공식 기사",
                "https://news.example.test/official",
                None,
            ),
            ParsedSource(
                2,
                "가상 행사 소식",
                "https://news.example.test@attacker.test/b",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
            ("가상 행사", "가상 행사 공식 기사"),
            ("가상 행사", "가상 행사 소식"),
        }),
    )

    screening = screen_candidate_sources(candidate, policy, rules)

    assert tuple(
        source.canonical_url
        for source in screening.valid_sources
    ) == (
        "https://news.example.test/official",
    )
    assert screening.source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        SourceIssue(2, SourceIssueCode.SOURCE_URL_INVALID),
    )



# ---------------------------------------------------------------------
# V-11: 기타 Category 근거 검증 및 CATEGORY_UNCLEAR
# ---------------------------------------------------------------------


def make_v11_catalog() -> CategoryCatalog:
    """Frozen 분류명을 사용한 합성 Catalog. ID는 테스트 전용이다."""
    return CategoryCatalog(
        roots=(
            CategoryRoot(10, "ENTERTAINMENT", True),
            CategoryRoot(20, "FASHION", True),
            CategoryRoot(30, "BEAUTY", False),
            CategoryRoot(40, "GAME", True),
        ),
        children=(
            CategoryChild(101, 10, "음악", True),
            CategoryChild(199, 10, "기타", True),
            CategoryChild(299, 20, "기타", False),
            CategoryChild(399, 30, "기타", True),
            CategoryChild(401, 40, "PC 게임", True),
        ),
    )


def make_v11_screening() -> tuple[
    ParsedCandidate,
    SourceScreeningResult,
]:
    candidate = make_candidate(
        "  가상   행사  ",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사",
                "https://news.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "가상 행사 추가 기사",
                "https://unknown.example.test/b",
                None,
            ),
        ),
    )
    screening = screen_candidate_sources(
        candidate,
        DomainPolicy(
            approved_hosts=frozenset({"news.example.test"}),
            blocked_hosts=frozenset(),
        ),
        FixtureSourceRelevanceRules(
            related=frozenset({
                ("가상 행사", "가상 행사 기사"),
            }),
        ),
    )

    return candidate, screening


def test_v11_other_selected_with_explicit_evidence() -> None:
    catalog = make_v11_catalog()

    selected = resolve_other_category_ids(
        catalog,
        root_id=10,
        evidence=OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
    )

    assert selected == (199,)


@pytest.mark.parametrize(
    "evidence",
    [
        OtherCategoryEvidence.UNDETERMINED,
        OtherCategoryEvidence.SPECIFIC_CHILD_APPLIES,
    ],
)
def test_v11_other_not_used_without_exclusion_evidence(
    evidence: OtherCategoryEvidence,
) -> None:
    assert resolve_other_category_ids(
        make_v11_catalog(),
        root_id=10,
        evidence=evidence,
    ) is None


@pytest.mark.parametrize(
    "root_id",
    [
        None,
        999,
        20,
        30,
        40,
    ],
)
def test_v11_other_requires_available_root_and_child(
    root_id: int | None,
) -> None:
    catalog = make_v11_catalog()

    assert resolve_other_category_ids(
        catalog,
        root_id,
        OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
    ) is None


def test_v11_duplicate_other_children_are_policy_error() -> None:
    catalog = CategoryCatalog(
        roots=(CategoryRoot(10, "ENTERTAINMENT", True),),
        children=(
            CategoryChild(198, 10, "기타", True),
            CategoryChild(199, 10, "기타", True),
        ),
    )

    with pytest.raises(ValidationExecutionError):
        resolve_other_category_ids(
            catalog,
            10,
            OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
        )


def test_v11_insufficient_evidence_returns_category_unclear() -> None:
    candidate, screening = make_v11_screening()
    catalog = make_v11_catalog()

    proposed_ids = resolve_other_category_ids(
        catalog,
        10,
        OtherCategoryEvidence.UNDETERMINED,
    )

    assert proposed_ids is None
    assert len(screening.valid_sources) == 1

    result = evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        catalog,
        proposed_ids,
    )

    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.CATEGORY_UNCLEAR,),
        normalized_title="가상 행사",
        valid_sources=(),
        category_ids=(),
        warnings=(WarningCode.INVALID_PUB_DATE,),
        source_issues=(
            SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        ),
    )


def test_v11_confirmed_other_proceeds_to_later_decision() -> None:
    candidate, screening = make_v11_screening()
    catalog = make_v11_catalog()

    selected = resolve_other_category_ids(
        catalog,
        10,
        OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
    )

    assert selected == (199,)

    assert evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        catalog,
        selected,
    ) is None


def test_v11_source_shortage_has_priority_over_category() -> None:
    candidate = make_candidate("가상 행사")
    screening = SourceScreeningResult(
        valid_sources=(),
        source_issues=(),
    )

    assert evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        make_v11_catalog(),
        None,
    ) is None


@pytest.mark.parametrize(
    "event_consistency",
    [
        EventConsistency.AMBIGUOUS,
        EventConsistency.UNDETERMINED,
    ],
)
def test_v11_event_ambiguity_has_priority(
    event_consistency: EventConsistency,
) -> None:
    candidate, screening = make_v11_screening()

    assert evaluate_category_unclear_gate(
        candidate,
        screening,
        event_consistency,
        make_v11_catalog(),
        None,
    ) is None


@pytest.mark.parametrize(
    "proposed_ids",
    [
        (10,),
        (299,),
        (999,),
    ],
)
def test_v11_invalid_child_selection_is_deferred(
    proposed_ids: tuple[int, ...],
) -> None:
    candidate, screening = make_v11_screening()

    result = evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        make_v11_catalog(),
        proposed_ids,
    )

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (ReasonCode.CATEGORY_UNCLEAR,)
    assert result.category_ids == ()
    assert result.valid_sources == ()



# ---------------------------------------------------------------------
# V-12: 동일 Fixture 및 정책의 반복 실행 결정성 검증
# ---------------------------------------------------------------------


def test_v12_source_screening_order_is_deterministic() -> None:
    candidate = make_candidate(
        "가상 행사",
        sources=(
            ParsedSource(
                0,
                "가상 행사 기사 0",
                "https://news.example.test/a?utm_source=rss&id=0",
                None,
            ),
            ParsedSource(
                1,
                "가상 행사 기사 1",
                "https://unknown.example.test/b",
                None,
            ),
            ParsedSource(
                2,
                "가상 행사 기사 2",
                "https://blocked.example.test/c",
                None,
            ),
            ParsedSource(
                3,
                "가상 행사 기사 3",
                "https://news.example.test/d?utm_source=rss&id=3",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset({"blocked.example.test"}),
    )
    rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", f"가상 행사 기사 {index}")
            for index in range(4)
        }),
    )

    snapshots = tuple(
        screen_candidate_sources(candidate, policy, rules)
        for _ in range(10)
    )

    assert all(result == snapshots[0] for result in snapshots)

    assert tuple(
        source.canonical_url
        for source in snapshots[0].valid_sources
    ) == (
        "https://news.example.test/a?id=0",
        "https://news.example.test/d?id=3",
    )

    assert snapshots[0].source_issues == (
        SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        SourceIssue(2, SourceIssueCode.BLOCKED_SOURCE_DOMAIN),
    )


def test_v12_unknown_domain_deferred_result_is_deterministic() -> None:
    candidate = make_candidate(
        "가상 행사",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(
            ParsedSource(
                0,
                "첫 번째 기사",
                "https://unknown-one.example.test/a",
                None,
            ),
            ParsedSource(
                1,
                "두 번째 기사",
                "https://unknown-two.example.test/b",
                None,
            ),
        ),
    )
    policy = DomainPolicy(
        approved_hosts=frozenset(),
        blocked_hosts=frozenset(),
    )
    rules = FixtureSourceRelevanceRules()

    results: list[CandidateEvaluation] = []

    for _ in range(10):
        screening = screen_candidate_sources(
            candidate, policy, rules
        )
        result = evaluate_unknown_domain_gate(candidate, screening)

        assert result is not None
        results.append(result)

    assert all(result == results[0] for result in results)

    assert results[0].decision == CandidateDecision.DEFERRED
    assert results[0].reason_codes == (
        ReasonCode.NO_ELIGIBLE_SOURCE,
        ReasonCode.UNKNOWN_SOURCE_DOMAIN,
    )
    assert results[0].source_issues == (
        SourceIssue(0, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
        SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )
    assert results[0].warnings == (WarningCode.INVALID_PUB_DATE,)


def test_v12_event_ambiguity_result_is_deterministic() -> None:
    candidate = make_v07_candidate(
        "news.example.test",
        warnings=(WarningCode.INVALID_PUB_DATE,),
    )
    topic_rules = FixtureTopicRules({})
    event_rules = FixtureEventRules({
        "가상 축제 A 개막": "event-a",
        "가상 축제 B 일정": "event-b",
    })

    def second_stage(
        current: ParsedCandidate,
    ) -> CandidateEvaluation:
        screening = screen_v07_candidate(current)

        assert len(screening.valid_sources) == 2

        result = evaluate_event_consistency_gate(
            current, screening, event_rules
        )

        assert result is not None
        return result

    results = tuple(
        evaluate_candidate(candidate, topic_rules, second_stage)
        for _ in range(10)
    )

    assert all(result == results[0] for result in results)
    assert results[0].decision == CandidateDecision.DEFERRED
    assert results[0].reason_codes == (
        ReasonCode.EVENT_AMBIGUOUS,
    )
    assert results[0].valid_sources == ()
    assert results[0].category_ids == ()


def test_v12_category_unclear_result_is_deterministic() -> None:
    results: list[CandidateEvaluation] = []

    for _ in range(10):
        candidate, screening = make_v11_screening()
        catalog = make_v11_catalog()

        selected = resolve_other_category_ids(
            catalog,
            10,
            OtherCategoryEvidence.UNDETERMINED,
        )

        result = evaluate_category_unclear_gate(
            candidate,
            screening,
            EventConsistency.CONSISTENT,
            catalog,
            selected,
        )

        assert result is not None
        results.append(result)

    assert all(result == results[0] for result in results)
    assert results[0].reason_codes == (
        ReasonCode.CATEGORY_UNCLEAR,
    )
    assert results[0].source_issues == (
        SourceIssue(1, SourceIssueCode.UNKNOWN_SOURCE_DOMAIN),
    )
    assert results[0].valid_sources == ()
    assert results[0].category_ids == ()


def test_v12_active_child_order_is_deterministic() -> None:
    results = tuple(
        make_v06_catalog().select_active_child_ids(
            (201, 101, 201, 102)
        )
        for _ in range(10)
    )

    assert results == ((101, 102, 201),) * 10


def test_v12_explicit_other_selection_is_deterministic() -> None:
    results = tuple(
        resolve_other_category_ids(
            make_v11_catalog(),
            10,
            OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
        )
        for _ in range(10)
    )

    assert results == ((199,),) * 10



# ---------------------------------------------------------------------
# V-13: 미반영 스포츠 및 비활성 Child Category 보류
# ---------------------------------------------------------------------


def make_v13_sports_case() -> tuple[
    ParsedCandidate,
    SourceScreeningResult,
]:
    """스포츠 관련 합성 후보. Source는 승인 및 관련성 검증 통과."""
    candidate = make_candidate(
        "가상 농구 경기",
        warnings=(WarningCode.INVALID_PUB_DATE,),
        sources=(
            ParsedSource(
                0,
                "가상 농구 경기 결과",
                "https://news.example.test/sports/1",
                None,
            ),
        ),
    )
    screening = screen_candidate_sources(
        candidate,
        DomainPolicy(
            approved_hosts=frozenset({"news.example.test"}),
            blocked_hosts=frozenset(),
        ),
        FixtureSourceRelevanceRules(
            related=frozenset({
                ("가상 농구 경기", "가상 농구 경기 결과"),
            }),
        ),
    )
    return candidate, screening


def test_v13_unrepresented_sports_is_deferred() -> None:
    candidate, screening = make_v13_sports_case()
    catalog = make_v11_catalog()

    assert len(screening.valid_sources) == 1
    assert screening.source_issues == ()
    assert all(child.name != "스포츠" for child in catalog.children)

    # 스포츠 검색어라는 이유만으로 1차 조기 제외하지 않는다.
    assert evaluate_topic_gate(
        candidate, FixtureTopicRules({})
    ) is None

    def second_stage(current: ParsedCandidate) -> CandidateEvaluation:
        result = evaluate_category_unclear_gate(
            current,
            screening,
            EventConsistency.CONSISTENT,
            catalog,
            proposed_child_ids=None,
        )
        assert result is not None
        return result

    result = evaluate_candidate(
        candidate,
        FixtureTopicRules({}),
        second_stage,
    )

    assert result == CandidateEvaluation(
        decision=CandidateDecision.DEFERRED,
        reason_codes=(ReasonCode.CATEGORY_UNCLEAR,),
        normalized_title="가상 농구 경기",
        valid_sources=(),
        category_ids=(),
        warnings=(WarningCode.INVALID_PUB_DATE,),
        source_issues=(),
    )


def test_v13_sports_does_not_automatically_use_other() -> None:
    catalog = make_v11_catalog()

    assert all(root.code != "SPORTS" for root in catalog.roots)

    # 식별 가능한 Root 자체가 없으면 기타를 선택할 수 없다.
    assert resolve_other_category_ids(
        catalog,
        root_id=None,
        evidence=OtherCategoryEvidence.NO_SPECIFIC_CHILD_APPLIES,
    ) is None

    # 다른 Root가 존재하더라도 배제 근거가 없다면 기타로 우회 금지.
    assert resolve_other_category_ids(
        catalog,
        root_id=10,
        evidence=OtherCategoryEvidence.UNDETERMINED,
    ) is None


@pytest.mark.parametrize(
    "proposed_ids",
    [
        pytest.param((999,), id="unknown-child"),
        pytest.param((10,), id="root-id-instead-of-child"),
        pytest.param((401, 999), id="active-plus-unknown"),
    ],
)
def test_v13_unsupported_category_ids_are_deferred(
    proposed_ids: tuple[int, ...],
) -> None:
    candidate, screening = make_v13_sports_case()

    result = evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        make_v11_catalog(),
        proposed_ids,
    )

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (ReasonCode.CATEGORY_UNCLEAR,)
    assert result.valid_sources == ()
    assert result.category_ids == ()


@pytest.mark.parametrize(
    "proposed_ids",
    [
        pytest.param((299,), id="inactive-child"),
        pytest.param((399,), id="inactive-parent-root"),
    ],
)
def test_v13_inactive_child_or_parent_is_deferred(
    proposed_ids: tuple[int, ...],
) -> None:
    candidate, screening = make_v13_sports_case()

    result = evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        make_v11_catalog(),
        proposed_ids,
    )

    assert result is not None
    assert result.decision == CandidateDecision.DEFERRED
    assert result.reason_codes == (ReasonCode.CATEGORY_UNCLEAR,)
    assert result.category_ids == ()
    assert result.valid_sources == ()


def test_v13_active_and_inactive_children_cannot_be_partially_accepted() -> None:
    candidate, screening = make_v13_sports_case()
    catalog = make_v11_catalog()

    # 활성 Child가 하나 포함되어도 비활성 Child를 무시하고
    # 부분 채택하는 방식으로 처리하지 않는다.
    assert catalog.select_active_child_ids((401, 299)) is None

    result = evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        catalog,
        (401, 299),
    )

    assert result is not None
    assert result.reason_codes == (ReasonCode.CATEGORY_UNCLEAR,)
    assert result.category_ids == ()


def test_v13_supported_active_child_proceeds_to_later_validation() -> None:
    candidate = make_candidate(
        "가상 PC 게임",
        sources=(
            ParsedSource(
                0,
                "가상 PC 게임 업데이트",
                "https://news.example.test/game",
                None,
            ),
        ),
    )
    screening = screen_candidate_sources(
        candidate,
        DomainPolicy(
            approved_hosts=frozenset({"news.example.test"}),
            blocked_hosts=frozenset(),
        ),
        FixtureSourceRelevanceRules(
            related=frozenset({
                ("가상 pc 게임", "가상 pc 게임 업데이트"),
            }),
        ),
    )
    catalog = make_v11_catalog()

    assert len(screening.valid_sources) == 1
    assert catalog.select_active_child_ids((401,)) == (401,)

    assert evaluate_category_unclear_gate(
        candidate,
        screening,
        EventConsistency.CONSISTENT,
        catalog,
        (401,),
    ) is None


def test_v13_category_catalog_is_not_mutated() -> None:
    candidate, screening = make_v13_sports_case()
    catalog = make_v11_catalog()

    before = (catalog.roots, catalog.children)

    for _ in range(3):
        result = evaluate_category_unclear_gate(
            candidate,
            screening,
            EventConsistency.CONSISTENT,
            catalog,
            proposed_child_ids=(999,),
        )
        assert result is not None
        assert result.decision == CandidateDecision.DEFERRED

    assert (catalog.roots, catalog.children) == before
    assert all(child.category_id != 999 for child in catalog.children)



# ---------------------------------------------------------------------
# V-14: P0~P3 외부 I/O 및 자동 게시 안전 경계
# ---------------------------------------------------------------------


_V14_ALLOWED_IMPORTS = frozenset({
    "__future__",
    "collections.abc",
    "dataclasses",
    "datetime",
    "email.utils",
    "enum",
    "hashlib",
    "ipaddress",
    "re",
    "typing",
    "unicodedata",
    "urllib.parse",
    "xml.etree.ElementTree",
    "defusedxml",
    "defusedxml.ElementTree",
    "app.external_trends.errors",
    "app.external_trends.types",
})

_V14_ALLOWED_RELATIVE_IMPORTS = frozenset({
    "errors",
    "normalizer",
    "types",
})


def test_v14_poc_modules_do_not_import_io_dependencies() -> None:
    """PoC 모듈의 정적 의존성을 안전한 범위로 제한한다."""
    package_dir = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "external_trends"
    )

    source_files = sorted(package_dir.rglob("*.py"))
    assert source_files

    for source_file in source_files:
        tree = ast.parse(
            source_file.read_text(encoding="utf-8"),
            filename=str(source_file),
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in _V14_ALLOWED_IMPORTS, (
                        f"unexpected import: {source_file}: "
                        f"{alias.name}"
                    )

            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    assert (
                        node.level == 1
                        and node.module in _V14_ALLOWED_RELATIVE_IMPORTS
                    ), (
                        f"unexpected relative import: "
                        f"{source_file}: {node.module}"
                    )
                else:
                    assert node.module in _V14_ALLOWED_IMPORTS, (
                        f"unexpected import: "
                        f"{source_file}: {node.module}"
                    )

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in {
                        "__import__",
                        "eval",
                        "exec",
                    }, (
                        f"unexpected dynamic execution: "
                        f"{source_file}: {node.func.id}"
                    )


@pytest.mark.parametrize(
    ("source_url", "is_approved"),
    [
        pytest.param(
            "https://news.example.test/a",
            True,
            id="approved-source",
        ),
        pytest.param(
            "https://unknown.example.test/a",
            False,
            id="unknown-source",
        ),
    ],
)
def test_v14_poc_pipeline_works_with_io_blocked(
    source_url: str,
    is_approved: bool,
) -> None:
    """외부 파일·네트워크·DB 접근을 차단한 상태에서 검증한다."""
    xml_bytes = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss
        version="2.0"
        xmlns:ht="https://trends.google.com/trending/rss"
    >
      <channel>
        <item>
          <title>가상 행사</title>
          <ht:news_item>
            <ht:news_item_title>가상 행사 기사</ht:news_item_title>
            <ht:news_item_url>{source_url}</ht:news_item_url>
          </ht:news_item>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    policy = DomainPolicy(
        approved_hosts=frozenset({"news.example.test"}),
        blocked_hosts=frozenset(),
    )
    relevance_rules = FixtureSourceRelevanceRules(
        related=frozenset({
            ("가상 행사", "가상 행사 기사"),
        }),
    )
    topic_rules = FixtureTopicRules({})

    # 모든 입력은 위에서 작성한 합성 XML bytes와 정책 값이다.
    # 검증 중 파일·네트워크·SQLite 호출을 허용하지 않는다.
    with (
        patch(
            "builtins.open",
            side_effect=AssertionError("file I/O is forbidden"),
        ),
        patch(
            "socket.create_connection",
            side_effect=AssertionError("network I/O is forbidden"),
        ),
        patch(
            "socket.socket.connect",
            side_effect=AssertionError("network I/O is forbidden"),
        ),
        patch(
            "sqlite3.connect",
            side_effect=AssertionError("DB I/O is forbidden"),
        ),
    ):
        parsed = parse_rss_feed(xml_bytes)

        assert len(parsed.candidates) == 1
        candidate = parsed.candidates[0]

        assert evaluate_topic_gate(candidate, topic_rules) is None

        screening = screen_candidate_sources(
            candidate,
            policy,
            relevance_rules,
        )

        if is_approved:
            assert len(screening.valid_sources) == 1

            event_result = evaluate_event_consistency_gate(
                candidate,
                screening,
                FixtureEventRules({
                    "가상 행사 기사": "event-a",
                }),
            )

            assert event_result is None

            category_result = evaluate_category_unclear_gate(
                candidate,
                screening,
                EventConsistency.CONSISTENT,
                make_v11_catalog(),
                proposed_child_ids=(101,),
            )

            # Source·사건·Category 단계 통과.
            # 아직 최종 WOULD_ACCEPT 생성 경로는 구현하지 않았다.
            assert category_result is None

        else:
            assert screening.valid_sources == ()

            result = evaluate_unknown_domain_gate(
                candidate,
                screening,
            )

            assert result is not None
            assert result.decision == CandidateDecision.DEFERRED
            assert result.reason_codes == (
                ReasonCode.NO_ELIGIBLE_SOURCE,
                ReasonCode.UNKNOWN_SOURCE_DOMAIN,
            )
            assert result.valid_sources == ()
            assert result.category_ids == ()
