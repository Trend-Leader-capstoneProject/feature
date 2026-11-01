
"""P3 V-01 — 명백한 범위 밖 검색어만 1차에서 제외한다."""

from dataclasses import dataclass
from hashlib import sha256

import pytest

from app.external_trends.candidate_validator import (
    CategoryCatalog,
    CategoryChild,
    CategoryRoot,
    DomainPolicy,
    EventConsistency,
    SourceRelevance,
    SourceScreeningResult,
    TopicScope,
    ValidationExecutionError,
    evaluate_candidate,
    evaluate_event_consistency_gate,
    evaluate_missing_or_invalid_source_gate,
    evaluate_relevance_unclear_gate,
    evaluate_topic_gate,
    evaluate_unknown_domain_gate,
    screen_candidate_sources,
)
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
