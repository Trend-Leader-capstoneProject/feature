"""No network, DB, publication or arbitrary SearchApi calls."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.trend_collection.searchapi_discovery import NewsLead, TrendingLead
from app.trend_collection.searchapi_evidence import (
    ArticleObservation,
    ProposedFact,
    assess_cross_source_evidence,
    build_review_event_identity,
)

NOW = datetime(2026, 11, 23, 10, tzinfo=timezone.utc)
YNA = "https://www.yna.co.kr/view/AKR20261123042700005"
NEWSIS = "https://mobile.newsis.com/view/NISX20261123_0003878761"

# Synthetic, *not actual* copied original article body text.
YNA_BODY = (
    "연예 소식입니다. 제작사 TEO는 음악 예능 굿데이 시즌2 제작과 "
    "2027년 상반기 공개 계획을 발표했습니다. 관련 출연진에 관한 "
    "추가 정보와 프로그램 제작 일정은 나중에 안내될 예정이라고 "
    "기사에서 전했습니다. 이 문장은 격리 테스트용입니다."
)
NEWSIS_BODY = (
    "프로그램 굿데이 시즌2가 다시 제작됩니다. 제작사 테오는 "
    "내년 상반기 공개 계획을 알렸습니다. 출연자들은 프로그램의 "
    "새로운 음악 프로젝트를 준비한다고 밝혔습니다. 이 본문은 "
    "실제 원문에서 복사한 기사가 아니라 테스트를 위해 만든 문장입니다."
)


def inputs():
    lead = TrendingLead(
        "지드래곤",
        datetime(2026, 11, 22, 13, 30, tzinfo=timezone.utc),
        "test-only-token",
        frozenset({"ENTERTAINMENT"}),
    )
    news = (
        NewsLead("굿데이 시즌2", YNA, "연합뉴스", NOW - timedelta(hours=9)),
        NewsLead("굿데이2", NEWSIS, "뉴시스", NOW - timedelta(hours=8)),
    )
    originals = (
        ArticleObservation(YNA, YNA_BODY, news[0].published_at_utc, NOW),
        ArticleObservation(NEWSIS, NEWSIS_BODY, news[1].published_at_utc, NOW),
    )
    fact = ProposedFact(
        "good-day-2-2027-h1-announcement",
        "ENTERTAINMENT",
        (("굿데이",), ("시즌2",), ("상반기",), ("공개",)),
    )
    return lead, news, originals, fact


def assess(*, news=None, originals=None, fact=None, now=NOW):
    lead, normal_news, normal_originals, normal_fact = inputs()
    return assess_cross_source_evidence(
        lead,
        normal_news if news is None else news,
        normal_originals if originals is None else originals,
        normal_fact if fact is None else fact,
        now=now,
    )


def test_two_different_article_bodies_only_reach_review_not_publication():
    decision = assess()
    assert decision.status == "REVIEW_REQUIRED"
    assert decision.reason == (
        "TWO_ARTICLE_BODIES_CONTAIN_ASSERTIONS_NOT_INDEPENDENT_PROOF"
    )
    assert decision.publish_authorization == "NONE"
    assert decision.urls == tuple(sorted((YNA, NEWSIS)))
    assert len(decision.evidence_ref) == 64
    assert not hasattr(decision, "source_key")
    assert not hasattr(decision, "proposed_status")



def test_evidence_digest_is_bound_to_original_body_content():
    _, _, originals, _ = inputs()
    base = assess()
    changed = replace(originals[1], body_text=NEWSIS_BODY + " 부가 설명.")
    updated = assess(originals=(originals[0], changed))
    assert base.status == updated.status == "REVIEW_REQUIRED"
    assert base.evidence_ref != updated.evidence_ref


def test_evidence_order_does_not_change_digest():
    _, _, originals, _ = inputs()
    assert assess().evidence_ref == assess(
        originals=(originals[1], originals[0]),
    ).evidence_ref


def test_raw_searchapi_metadata_cannot_establish_article_evidence():
    assert assess(originals=()).reason == "TWO_ORIGINAL_ARTICLES_REQUIRED"


def test_title_only_cannot_prove_article_body():
    _, _, originals, _ = inputs()
    fake = replace(originals[0], body_text="굿데이 시즌2 상반기 공개")
    assert assess(originals=(fake, originals[1])).reason == (
        "ORIGINAL_ARTICLE_BODY_REQUIRED"
    )


def test_article_body_must_support_every_proposed_assertion():
    _, _, originals, _ = inputs()
    fake = replace(
        originals[0],
        body_text=("연예 소식입니다. 굿데이 시즌2 제작은 확인했지만 "
                   "정식 날짜와 시기 정보를 다루지 않습니다. "
                   "실제 원문이 아니라 테스트용 기사 본문입니다." * 2),
    )
    assert assess(originals=(fake, originals[1])).reason == (
        "FACT_NOT_SUPPORTED_IN_ARTICLE_BODY"
    )


def test_two_urls_of_same_publication_do_not_pass():
    _, news, originals, _ = inputs()
    extra_url = "https://amp.yna.co.kr/view/AKR20261123042700005"
    same_news = (news[0], replace(news[1], url=extra_url))
    assert assess(
        news=same_news,
        originals=(originals[0], replace(originals[1], source_url=extra_url)),
    ).reason == "SAME_PUBLISHER_ORIGIN"


def test_syndicated_identical_bodies_are_held():
    _, _, originals, _ = inputs()
    assert assess(
        originals=(originals[0], replace(originals[1], body_text=YNA_BODY)),
    ).reason == "IDENTICAL_REPRINT"


def test_unrelated_original_url_is_not_corroborating_evidence():
    _, _, originals, _ = inputs()
    unlisted = replace(originals[1], source_url="https://another.example.com/article")
    assert assess(originals=(originals[0], unlisted)).reason == (
        "ARTICLE_LINK_NOT_IN_NEWS"
    )


def test_recent_article_retrieval_is_required():
    _, _, originals, _ = inputs()
    stale = replace(originals[1], retrieved_at_utc=NOW - timedelta(minutes=11))
    assert assess(originals=(originals[0], stale)).reason == (
        "EVIDENCE_STALE_OR_TIME_MISMATCH"
    )


def test_future_article_is_rejected():
    _, _, originals, _ = inputs()
    future = replace(originals[1], published_at_utc=NOW + timedelta(days=1))
    assert assess(originals=(originals[0], future)).reason == (
        "EVIDENCE_STALE_OR_TIME_MISMATCH"
    )


def test_invalid_root_hint_cannot_be_promoted():
    _, _, _, fact = inputs()
    assert assess(fact=replace(fact, root_code="GAME")).reason == (
        "INVALID_FACT_PROPOSAL"
    )


def test_publisher_name_is_not_a_source_identity():
    _, news, _, _ = inputs()
    spoofed = tuple(replace(n, publisher="동일한 보도자료") for n in news)
    # Same source descriptions still cannot assert independent reporting.
    result = assess(news=spoofed)
    assert result.status == "REVIEW_REQUIRED"
    assert result.publish_authorization == "NONE"


def test_news_metadata_timestamps_must_match_article_observations():
    _, news, _, _ = inputs()
    mismatch = (news[0], replace(
        news[1], published_at_utc=NOW - timedelta(days=3),
    ))
    assert assess(news=mismatch).reason == "EVIDENCE_STALE_OR_TIME_MISMATCH"


def test_non_public_link_is_rejected():
    _, news, originals, _ = inputs()
    private = "https://127.0.0.1/article"
    bad = (news[0], replace(news[1], url=private))
    result = assess(
        news=bad, originals=(originals[0], replace(originals[1], source_url=private)),
    )
    assert result.reason == "INVALID_NEWS_METADATA"
    assert result.status == "HOLD"
    assert result.publish_authorization == "NONE"

def test_malformed_metadata_urls_fail_closed_without_type_errors():
    _, news, originals, _ = inputs()
    malformed = (news[0], replace(news[1], url=["not", "a", "url"]))
    assert assess(news=malformed).reason == "INVALID_NEWS_METADATA"
    malformed_observation = replace(originals[1], source_url=["bad"])
    assert assess(
        originals=(originals[0], malformed_observation),
    ).reason == "ORIGINAL_ARTICLE_REQUIRED"


def test_keyword_corroboration_is_not_semantic_truth_proof():
    _, _, originals, _ = inputs()
    # Contains all tokens but explicitly denies the claimed future release.
    denying = replace(
        originals[0],
        body_text=(
            "굿데이 시즌2가 상반기 공개된다는 주장은 사실이 아니다. "
            "제작 시점은 아직 확인할 수 없다고 밝혔다. "
            "이는 원문 기사 사실을 나타내지 않는 테스트 문장이다. "
        ) * 2,
    )
    assessment = assess(originals=(denying, originals[1]))
    assert assessment.status == "REVIEW_REQUIRED"
    assert assessment.publish_authorization == "NONE"


def test_review_event_identity_is_stable_when_article_text_changes():
    _, _, original_observations, fact = inputs()
    original = assess()
    changed = assess(originals=(
        original_observations[0],
        replace(original_observations[1], body_text=NEWSIS_BODY + " 추가 내용"),
    ))
    first = build_review_event_identity(fact, original)
    second = build_review_event_identity(fact, changed)
    assert first is not None and second is not None
    assert first.candidate_identity == second.candidate_identity
    assert first.candidate_identity == (
        "searchapi-event:good-day-2-2027-h1-announcement"
    )
    assert first.external_id == first.candidate_identity
    assert first.source_key == sha256(
        f"ETC:{first.external_id}".encode("utf-8"),
    ).hexdigest()
    assert first.evidence_ref != second.evidence_ref
    assert first.publish_authorization == second.publish_authorization == "NONE"
    assert first.proposed_status == second.proposed_status == "HIDDEN"


def test_review_only_identity_requires_evidence_and_valid_case_key():
    _, _, _, fact = inputs()
    assert build_review_event_identity(fact, assess(originals=())) is None
    assert build_review_event_identity(
        replace(fact, review_case_key="invalid case with spaces"), assess(),
    ) is None


def test_review_only_identity_cannot_pass_writer_freshness_guard():
    from app.trend_collection.freshness_policy import (
        validate_snapshot_freshness,
    )
    from app.trend_collection.supply_adapter import SupplyBlocked

    _, _, _, fact = inputs()
    candidate = build_review_event_identity(fact, assess())
    assert candidate is not None
    with pytest.raises(SupplyBlocked, match="SNAPSHOT_TYPE_NOT_SUPPORTED"):
        validate_snapshot_freshness(
            SimpleNamespace(source=lambda _: None), candidate, NOW,
        )
