from hashlib import sha256
from typing import cast

import pytest

from app.external_trends.normalizer import (
    NormalizedTitle,
    extract_candidate_hostname,
    normalize_source_url,
    normalize_title,
    remove_utm_tracking_from_url_unchecked,
    remove_utm_tracking_query,
)

# ---------------------------------------------------------------------
# N-01: Unicode NFC·공백 정규화 및 ASCII 대소문자 처리
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw_title", "display_title", "normalized_title"),
    [
        (
            " \tCafe\u0301 \u00a0AI \n 미래  ",
            "Café AI 미래",
            "café ai 미래",
        ),
        (
            "  Trend  LEADER  ",
            "Trend LEADER",
            "trend leader",
        ),
        (
            "CAFÉ Σ",
            "CAFÉ Σ",
            "cafÉ Σ",
        ),
    ],
)
def test_n01_normalizes_nfc_whitespace_and_ascii_only(
    raw_title: str,
    display_title: str,
    normalized_title: str,
) -> None:
    assert normalize_title(raw_title) == NormalizedTitle(
        display_title=display_title,
        normalized_title=normalized_title,
    )


def test_n01_equivalent_unicode_inputs_share_key() -> None:
    decomposed = normalize_title(" Cafe\u0301 AI ")
    composed = normalize_title("Café AI")

    assert decomposed is not None
    assert composed is not None
    assert decomposed.normalized_title == composed.normalized_title


def test_n01_accepts_exactly_255_codepoints() -> None:
    result = normalize_title("A" * 255)

    assert result is not None
    assert result.display_title == "A" * 255
    assert result.normalized_title == "a" * 255


@pytest.mark.parametrize(
    "raw_title",
    [" \t\u00a0\n ", "A" * 256],
    ids=["whitespace-only", "length-256"],
)
def test_n01_rejects_empty_or_oversized_title(raw_title: str) -> None:
    assert normalize_title(raw_title) is None


@pytest.mark.parametrize(
    "raw_title",
    [None, 123],
    ids=["none", "integer"],
)
def test_n01_rejects_non_string_input(raw_title: object) -> None:
    with pytest.raises(TypeError, match="raw_title must be str"):
        normalize_title(cast(str, raw_title))


# ---------------------------------------------------------------------
# N-02: 의미 있는 숫자·로마 숫자·기호 차이 보존
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right", "expected_left", "expected_right"),
    [
        ("AI IV", "AI Ⅳ", "ai iv", "ai Ⅳ"),
        ("Version 2", "Version Ⅱ", "version 2", "version Ⅱ"),
        ("C++", "C#", "c++", "c#"),
        ("Trend-A", "Trend A", "trend-a", "trend a"),
        ("Model 2026", "Model 2027", "model 2026", "model 2027"),
    ],
)
def test_n02_preserves_meaningful_distinctions(
    left: str,
    right: str,
    expected_left: str,
    expected_right: str,
) -> None:
    """숫자·로마 숫자·기호 차이를 임의로 병합하지 않는다."""
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)

    assert normalized_left is not None
    assert normalized_right is not None

    assert normalized_left.normalized_title == expected_left
    assert normalized_right.normalized_title == expected_right

    assert normalized_left.normalized_title != normalized_right.normalized_title



# ---------------------------------------------------------------------
# N-03: 정확히 지정된 UTM 추적 파라미터만 제거
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_query", "expected_query"),
    [
        (
            "utm_source=home&utm_medium=email&id=42"
            "&utm_campaign=launch&utm_term=ai&utm_content=top",
            "id=42",
        ),
        (
            "id=7&UTM_SOURCE=keep&utm_source_extra=keep&utm_source=drop",
            "id=7&UTM_SOURCE=keep&utm_source_extra=keep",
        ),
        (
            "utm_source&article=alpha",
            "article=alpha",
        ),
        (
            "utm_source=x&utm_medium=y",
            "",
        ),
        (
            "id=a%2Fb&note=x+y&utm_campaign=removed",
            "id=a%2Fb&note=x+y",
        ),
        (
            "article=utm_source&utm_term=x",
            "article=utm_source",
        ),
        (
            "id=2&%75tm_source=keep&utm_source=drop",
            "id=2&%75tm_source=keep",
        ),
    ],
)
def test_n03_removes_only_literal_utm_keys(
    raw_query: str,
    expected_query: str,
) -> None:
    """쿼리의 원래 표현을 유지하면서 지정된 UTM 키만 제거한다."""
    assert remove_utm_tracking_query(raw_query) == expected_query



# ---------------------------------------------------------------------
# N-04: URL의 경로·쿼리 순서·반복 키·Fragment 보존
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (
            "https://example.test/articles/ABC?"
            "id=42&utm_source=home&page=2#comments",
            "https://example.test/articles/ABC?id=42&page=2#comments",
        ),
        (
            "https://example.test/a%2Fb?"
            "article=alpha&page=1&page=2&utm_medium=email#part-2",
            "https://example.test/a%2Fb?"
            "article=alpha&page=1&page=2#part-2",
        ),
        (
            "https://example.test/case/Special%2FName?"
            "utm_campaign=launch#top",
            "https://example.test/case/Special%2FName#top",
        ),
        (
            "https://example.test/docs/Guide#utm_source=keep",
            "https://example.test/docs/Guide#utm_source=keep",
        ),
        (
            "https://example.test/path?"
            "utm_term=ai&note=a%2Bb+z&x=&x=2#section%2F1",
            "https://example.test/path?"
            "note=a%2Bb+z&x=&x=2#section%2F1",
        ),
        (
            "https://example.test/path?"
            "utm_source=first&utm_source=second&id=1#frag",
            "https://example.test/path?id=1#frag",
        ),
        (
            "https://example.test/path?"
            "id=42&%75tm_source=keep&utm_content=drop",
            "https://example.test/path?id=42&%75tm_source=keep",
        ),
        (
            "https://example.test/path?"
            "id=a=b&utm_source=drop&flag#f",
            "https://example.test/path?id=a=b&flag#f",
        ),
    ],
)
def test_n04_preserves_meaningful_url_components(
    raw_url: str,
    expected_url: str,
) -> None:
    """UTM만 제거하고 경로·쿼리 표현·Fragment를 보존한다."""
    assert remove_utm_tracking_from_url_unchecked(raw_url) == expected_url



# ---------------------------------------------------------------------
# N-05: 비ASCII 대소문자 보존 및 DB Collation 경계
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right", "expected_left", "expected_right"),
    [
        ("CAFÉ", "café", "cafÉ", "café"),
        ("Σ", "σ", "Σ", "σ"),
        ("İstanbul", "istanbul", "İstanbul", "istanbul"),
        ("Straße", "STRASSE", "straße", "strasse"),
        ("MÜNCHEN", "München", "mÜnchen", "münchen"),
    ],
)
def test_n05_preserves_non_ascii_case_distinctions(
    left: str,
    right: str,
    expected_left: str,
    expected_right: str,
) -> None:
    """ASCII 외의 대소문자 차이는 임의로 병합하지 않는다."""
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)

    assert normalized_left is not None
    assert normalized_right is not None

    assert normalized_left.normalized_title == expected_left
    assert normalized_right.normalized_title == expected_right

    assert normalized_left.normalized_title != normalized_right.normalized_title


def test_n05_does_not_apply_unicode_casefold() -> None:
    """casefold가 병합하는 제목도 FROZEN 규칙에서는 구별한다."""
    left = "Straße"
    right = "STRASSE"

    assert left.casefold() == right.casefold()

    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)

    assert normalized_left is not None
    assert normalized_right is not None

    assert normalized_left.normalized_title == "straße"
    assert normalized_right.normalized_title == "strasse"
    assert normalized_left.normalized_title != normalized_right.normalized_title



# ---------------------------------------------------------------------
# N-06: 위험 Scheme·사용자 정보·IP·localhost·도메인 사칭 방어
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_url", "expected_hostname"),
    [
        ("https://NEWS.Example.TEST/article", "news.example.test"),
        ("HTTP://NEWS.Example.TEST:80/article", "news.example.test"),
        ("https://NEWS.Example.TEST:443/article", "news.example.test"),
    ],
)
def test_n06_extracts_normalized_hostname(
    raw_url: str,
    expected_hostname: str,
) -> None:
    assert extract_candidate_hostname(raw_url) == expected_hostname


@pytest.mark.parametrize(
    "raw_url",
    [
        "javascript:alert(1)",
        "file:///tmp/example.xml",
        "ftp://news.example.test/article",
        "//news.example.test/article",
        "https:news.example.test/article",
        "https://user:password@news.example.test/article",
        "https://news.example.test@attacker.test/article",
        "https://127.0.0.1/article",
        "https://[::1]/article",
        "https://localhost/article",
        "https://sub.localhost/article",
        "https://127.1/article",
        "https://2130706433/article",
    ],
)
def test_n06_rejects_dangerous_url_candidates(raw_url: str) -> None:
    assert extract_candidate_hostname(raw_url) is None


def test_n06_spoof_hostname_is_not_approved_host() -> None:
    approved_host = "news.example.test"

    candidate = extract_candidate_hostname(
        "https://news.example.test.attacker.test/article"
    )

    assert candidate == "news.example.test.attacker.test"
    assert candidate != approved_host


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://bücher.example/article",
        "https://xn--bcher-kva.example/article",
    ],
)
def test_n06_idn_host_must_not_be_implicitly_approved(
    raw_url: str,
) -> None:
    candidate = extract_candidate_hostname(raw_url)

    assert candidate is not None
    assert candidate != "news.example.test"



# ---------------------------------------------------------------------
# N-07: 빈 포트·제어문자·역슬래시·모호한 호스트 방어
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_url",
    [
        pytest.param("https://news.example.test:", id="empty-https-port"),
        pytest.param(
            "https://news.example.test:/article",
            id="empty-port-with-path",
        ),
        pytest.param(
            "http://news.example.test:?id=1",
            id="empty-http-port",
        ),
        pytest.param(
            "https://news.example.test:abc/article",
            id="non-numeric-port",
        ),
        pytest.param(
            "https://news.example.test:65536/article",
            id="out-of-range-port",
        ),
        pytest.param(
            "https://news.example.test:8443/article",
            id="non-default-port",
        ),
        pytest.param(
            " https://news.example.test/article",
            id="leading-space",
        ),
        pytest.param(
            "https://news.example.test/a b",
            id="raw-space",
        ),
        pytest.param(
            "https://news.example.test/a\tb",
            id="raw-tab",
        ),
        pytest.param(
            "https://news.example.test/a\nb",
            id="raw-newline",
        ),
        pytest.param(
            "https://news.example.test/a\x00b",
            id="nul-control",
        ),
        pytest.param(
            "https://news.example.test/a\x7fb",
            id="del-control",
        ),
        pytest.param(
            r"https://news.example.test\@evil.test/a",
            id="backslash",
        ),
        pytest.param(
            "https://news.example.test./article",
            id="trailing-host-dot",
        ),
        pytest.param(
            "https://%6eews.example.test/article",
            id="encoded-host-letter",
        ),
        pytest.param(
            "https://news%2eexample.test/article",
            id="encoded-host-dot",
        ),
        pytest.param(
            "https:///article",
            id="missing-host",
        ),
        pytest.param(
            "https://news_example.test/article",
            id="invalid-host-label",
        ),
    ],
)
def test_n07_rejects_ambiguous_url_inputs(raw_url: str) -> None:
    """파서가 모호하게 해석할 수 있는 URL은 거부한다."""
    assert extract_candidate_hostname(raw_url) is None


@pytest.mark.parametrize(
    ("raw_url", "expected_hostname"),
    [
        (
            "https://NEWS.Example.TEST:443/a?id=1#top",
            "news.example.test",
        ),
        (
            "http://NEWS.Example.TEST:80/a?id=1",
            "news.example.test",
        ),
        (
            "https://news.example.test/a?x=1&x=2#frag",
            "news.example.test",
        ),
        (
            "https://bücher.example/a",
            "bücher.example",
        ),
    ],
)
def test_n07_keeps_valid_candidate_hosts(
    raw_url: str,
    expected_hostname: str,
) -> None:
    """비정상 입력을 거부하더라도 정상 호스트는 보존한다."""
    assert extract_candidate_hostname(raw_url) == expected_hostname


@pytest.mark.parametrize(
    ("target_length", "expected_hostname"),
    [
        (4096, "news.example.test"),
        (4097, None),
    ],
)
def test_n07_enforces_url_codepoint_limit(
    target_length: int,
    expected_hostname: str | None,
) -> None:
    """URL 원본 길이 4096 코드포인트까지 허용한다."""
    prefix = "https://news.example.test/"
    raw_url = prefix + "가" * (target_length - len(prefix))

    assert len(raw_url) == target_length
    assert extract_candidate_hostname(raw_url) == expected_hostname



# ---------------------------------------------------------------------
# N-08: 중복 UTM·인코딩된 키·반복 값·빈 쿼리 처리
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_query", "expected_query"),
    [
        (
            "id=1&utm_source=a&utm_source=b&utm_medium=x&id=2",
            "id=1&id=2",
        ),
        (
            "utm_content=a=1&utm_term=&article=abc=def",
            "article=abc=def",
        ),
        (
            "id=1&%75tm_source=encoded"
            "&utm%5Fsource=encoded&utm_source=drop",
            "id=1&%75tm_source=encoded&utm%5Fsource=encoded",
        ),
        (
            "UTM_SOURCE=keep&utm_source_extra=keep&utm_source=drop",
            "UTM_SOURCE=keep&utm_source_extra=keep",
        ),
        (
            "id=1&id=2&flag&x=&utm_campaign=drop",
            "id=1&id=2&flag&x=",
        ),
        (
            "id=1&&utm_source=drop&flag&",
            "id=1&&flag&",
        ),
        (
            "utm_source=home&utm_medium=email",
            "",
        ),
        (
            "note=a%26b%3Dc&utm_medium=mail&sort=x+y",
            "note=a%26b%3Dc&sort=x+y",
        ),
    ],
)
def test_n08_preserves_raw_query_representation(
    raw_query: str,
    expected_query: str,
) -> None:
    """정확한 UTM만 제거하고 나머지 쿼리 표현은 보존한다."""
    assert remove_utm_tracking_query(raw_query) == expected_query


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (
            "https://example.test/a?id=1&id=2"
            "&utm_source=one&utm_source=two#part",
            "https://example.test/a?id=1&id=2#part",
        ),
        (
            "https://example.test/a?utm_source=x&utm_medium=y#frag",
            "https://example.test/a#frag",
        ),
        (
            "https://example.test/a?utm_source=x&utm_campaign=y",
            "https://example.test/a",
        ),
        (
            "https://example.test/a?id=x%2Fy"
            "&%75tm_source=preserve&utm_term=drop#utm_source=frag",
            "https://example.test/a?id=x%2Fy"
            "&%75tm_source=preserve#utm_source=frag",
        ),
    ],
)
def test_n08_reassembles_urls_without_changing_remaining_parts(
    raw_url: str,
    expected_url: str,
) -> None:
    """중복 UTM 제거 후에도 유효한 쿼리와 Fragment를 보존한다."""
    assert remove_utm_tracking_from_url_unchecked(raw_url) == expected_url


def test_n08_url_cleanup_is_deterministic_and_idempotent() -> None:
    """동일 입력은 같은 결과를 내고 재적용해도 달라지지 않는다."""
    raw_url = (
        "https://example.test/a?id=1&id=2"
        "&utm_source=x&%75tm_source=keep#section"
    )

    first = remove_utm_tracking_from_url_unchecked(raw_url)
    second = remove_utm_tracking_from_url_unchecked(raw_url)
    repeated = remove_utm_tracking_from_url_unchecked(first)

    assert first == (
        "https://example.test/a?"
        "id=1&id=2&%75tm_source=keep#section"
    )
    assert first == second
    assert first == repeated



# ---------------------------------------------------------------------
# P2 통합: canonical URL 및 SHA-256 source_key 생성
# ---------------------------------------------------------------------




@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (
            "HTTPS://NEWS.Example.TEST:443/a?"
            "id=42&utm_source=home#section",
            "https://news.example.test/a?id=42#section",
        ),
        (
            "HTTP://NEWS.Example.TEST:80/a?"
            "utm_medium=x&article=2&article=3",
            "http://news.example.test/a?article=2&article=3",
        ),
        (
            "https://news.example.test/a%2Fb?"
            "%75tm_source=keep&utm_term=x",
            "https://news.example.test/a%2Fb?%75tm_source=keep",
        ),
        (
            "https://news.example.test/a?"
            "utm_source=x#comments",
            "https://news.example.test/a#comments",
        ),
    ],
)
def test_p2_url_integration_creates_canonical_url_and_key(
    raw_url: str,
    expected_url: str,
) -> None:
    result = normalize_source_url(raw_url)

    assert result is not None
    assert result.hostname == "news.example.test"
    assert result.canonical_url == expected_url
    assert result.source_key == sha256(
        expected_url.encode("utf-8")
    ).hexdigest()
    assert len(result.source_key) == 64
    assert result.source_key == result.source_key.lower()


@pytest.mark.parametrize(
    "raw_url",
    [
        "javascript:alert(1)",
        "https://user@news.example.test/a",
        "http://127.0.0.1/a",
        "https://news.example.test:",
        "https://news.example.test/a\nb",
    ],
)
def test_p2_url_integration_rejects_invalid_url(
    raw_url: str,
) -> None:
    assert normalize_source_url(raw_url) is None


def test_p2_url_integration_hashes_utf8_bytes() -> None:
    result = normalize_source_url(
        "https://news.example.test/한글?utm_source=x&id=7"
    )

    assert result is not None
    assert result.canonical_url == (
        "https://news.example.test/한글?id=7"
    )
    assert result.source_key == (
        "b95ecb938394a4a4d5e44bdee37d0d7e"
        "4c3a16635c25e584c5cb03cbf3d53c24"
    )


def test_p2_url_integration_same_canonical_url_same_key() -> None:
    first = normalize_source_url(
        "HTTPS://NEWS.Example.TEST:443/a?id=1&utm_source=x"
    )
    second = normalize_source_url(
        "https://news.example.test/a?id=1"
    )

    assert first is not None
    assert second is not None
    assert first == second


def test_p2_url_integration_preserves_meaningful_differences() -> None:
    urls = [
        "https://news.example.test/a?id=1",
        "https://news.example.test/a?id=2",
        "https://news.example.test/A?id=1",
        "https://news.example.test/a?id=1#comments",
    ]

    results = [normalize_source_url(url) for url in urls]

    assert all(result is not None for result in results)

    keys = {
        result.source_key
        for result in results
        if result is not None
    }

    assert len(keys) == 4


@pytest.mark.parametrize(
    ("target_length", "accepted"),
    [
        (4096, True),
        (4097, False),
    ],
)
def test_p2_url_integration_enforces_input_length(
    target_length: int,
    accepted: bool,
) -> None:
    prefix = "https://news.example.test/"
    raw_url = prefix + "가" * (target_length - len(prefix))

    result = normalize_source_url(raw_url)

    assert len(raw_url) == target_length
    assert (result is not None) is accepted



# ---------------------------------------------------------------------
# P2 Final Review: URL 정규화 경계 조건 회귀 검증
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_url", "expected_hostname"),
    [
        (
            "https://K.example.test/a",
            "K.example.test",
        ),
        (
            "https://NÉWS.example.test/a",
            "nÉws.example.test",
        ),
    ],
)
def test_p2_final_review_preserves_non_ascii_hostname(
    raw_url: str,
    expected_hostname: str,
) -> None:
    """Unicode 호스트가 ASCII 정규화에 의해 병합되지 않는다."""
    result = normalize_source_url(raw_url)

    assert result is not None
    assert result.hostname == expected_hostname
    assert result.canonical_url == f"https://{expected_hostname}/a"


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://0x7f.0x0.0x0.0x1/a",
        "https://news.example.test/a\x81b",
        "https://news.example.test/a\x9fb",
    ],
)
def test_p2_final_review_rejects_ambiguous_or_control_urls(
    raw_url: str,
) -> None:
    """IP 우회 표현과 C1 제어문자를 포함한 URL을 거부한다."""
    assert normalize_source_url(raw_url) is None
