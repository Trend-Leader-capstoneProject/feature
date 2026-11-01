
"""P3 V-01 — 명백한 범위 밖 검색어만 1차에서 제외한다."""

from dataclasses import dataclass
from hashlib import sha256

import pytest

from app.external_trends.candidate_validator import (
    DomainPolicy,
    SourceRelevance,
    SourceScreeningResult,
    TopicScope,
    evaluate_candidate,
    evaluate_missing_or_invalid_source_gate,
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
