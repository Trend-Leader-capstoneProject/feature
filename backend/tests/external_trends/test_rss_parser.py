from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from app.external_trends import rss_parser
from app.external_trends.errors import FeedParseError, FeedParseErrorCode
from app.external_trends.rss_parser import parse_rss_feed
from app.external_trends.types import (
    ItemIssue,
    ItemIssueCode,
    ParsedSource,
    WarningCode,
)

# ---------------------------------------------------------------------
# P-01: Namespace URI 기반 RSS 기사 파싱
# ---------------------------------------------------------------------

@pytest.mark.parametrize("prefix", ["ht", "news"])
def test_p01_parses_rss_item_using_namespace_uri(
    prefix: str,
) -> None:
    """동일 namespace URI라면 접두어와 무관하게 기사를 인식한다."""

    source_url = "https://articles.example.test/fictional/1"

    xml_bytes = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:{prefix}="https://trends.google.com/trending/rss">
      <channel>
        <title>가상 기술 소식</title>
        <item>
          <title>가상 기기 X3 출시</title>
          <{prefix}:news_item>
            <{prefix}:news_item_title>가상 기기 X3 출시 소식</{prefix}:news_item_title>
            <{prefix}:news_item_url>{source_url}</{prefix}:news_item_url>
            <{prefix}:news_item_source>가상 매체</{prefix}:news_item_source>
          </{prefix}:news_item>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == ()
    assert len(result.candidates) == 1

    candidate = result.candidates[0]

    assert candidate.item_index == 0
    assert candidate.raw_title == "가상 기기 X3 출시"
    assert candidate.rss_published_at is None
    assert candidate.warnings == ()

    assert candidate.source_candidates == (
        ParsedSource(
            item_news_index=0,
            raw_title="가상 기기 X3 출시 소식",
            raw_url=source_url,
            publisher_name="가상 매체",
        ),
    )


# ---------------------------------------------------------------------
# P-02: Item·기사 순서 및 중복 출처 보존
# ---------------------------------------------------------------------

P02_FIXTURE = Path(__file__).parent / "fixtures" / "valid_feed.xml"


def test_p02_accepts_zero_one_three_news_items_in_order() -> None:
    """기사 0/1/3건을 모두 허용하고 원본 Item 순서를 유지한다."""
    result = parse_rss_feed(P02_FIXTURE.read_bytes())

    assert result.item_issues == ()
    assert [candidate.item_index for candidate in result.candidates] == [0, 1, 2]
    assert [candidate.raw_title for candidate in result.candidates] == [
        "가상 기기 A",
        "가상 기기 B",
        "가상 기기 C",
    ]
    assert [len(candidate.source_candidates) for candidate in result.candidates] == [
        0,
        1,
        3,
    ]


def test_p02_preserves_news_indices_and_repeated_source_urls() -> None:
    """기사 원본 순서와 중복 URL을 P1 단계에서 제거하지 않는다."""
    result = parse_rss_feed(P02_FIXTURE.read_bytes())
    sources = result.candidates[2].source_candidates

    assert [source.item_news_index for source in sources] == [0, 1, 2]
    assert [source.raw_title for source in sources] == [
        "C 관련 기사 1",
        "C 관련 기사 2",
        "C 관련 기사 3",
    ]
    assert [source.raw_url for source in sources] == [
        "https://example.test/c/1",
        "https://example.test/c/2",
        "https://example.test/c/1",
    ]
    assert [source.publisher_name for source in sources] == [
        "가상 신문 C",
        "가상 신문 D",
        "가상 신문 E",
    ]


# ---------------------------------------------------------------------
# P-03: Item 제목 누락·공백 처리
# ---------------------------------------------------------------------

def test_p03_missing_and_blank_item_titles_are_reported() -> None:
    """누락된 제목만 제외하고 원래 Item 위치 및 원문은 유지한다."""
    xml_bytes = """<rss version="2.0">
      <channel>
        <item><description>제목 없음</description></item>
        <item><title>  가상 AI 연구  </title></item>
        <item><title></title></item>
        <item><title>   </title></item>
        <item><title>가상 게임 행사</title></item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == (
        ItemIssue(item_index=0, code=ItemIssueCode.MISSING_ITEM_TITLE),
        ItemIssue(item_index=2, code=ItemIssueCode.MISSING_ITEM_TITLE),
        ItemIssue(item_index=3, code=ItemIssueCode.MISSING_ITEM_TITLE),
    )

    assert [(item.item_index, item.raw_title) for item in result.candidates] == [
        (1, "  가상 AI 연구  "),
        (4, "가상 게임 행사"),
    ]

# ---------------------------------------------------------------------
# P-04: 선택 필드 누락·빈 값 허용
# ---------------------------------------------------------------------

def test_p04_empty_optional_fields_are_accepted() -> None:
    """빈 description과 snippet은 파싱 실패 사유가 아니다."""
    xml_bytes = """<rss version="2.0"
      xmlns:ht="https://trends.google.com/trending/rss">
      <channel>
        <item>
          <title>가상 기술 행사</title>
          <description></description>
          <ht:news_item>
            <ht:news_item_title>가상 행사 기사</ht:news_item_title>
            <ht:news_item_url>https://example.test/events/1</ht:news_item_url>
            <ht:news_item_source>가상 언론</ht:news_item_source>
            <ht:news_item_snippet/>
          </ht:news_item>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == ()
    assert len(result.candidates) == 1
    assert result.candidates[0].source_candidates == (
        ParsedSource(
            item_news_index=0,
            raw_title="가상 행사 기사",
            raw_url="https://example.test/events/1",
            publisher_name="가상 언론",
        ),
    )


def test_p04_missing_news_fields_are_preserved_as_none() -> None:
    """기사 필드가 누락되어도 Source를 삭제하지 않는다."""
    xml_bytes = """<rss version="2.0"
      xmlns:ht="https://trends.google.com/trending/rss">
      <channel>
        <item>
          <title>가상 제품 발표</title>
          <ht:news_item>
            <ht:news_item_url>https://example.test/news/1</ht:news_item_url>
          </ht:news_item>
          <ht:news_item>
            <ht:news_item_title>기사 B</ht:news_item_title>
            <ht:news_item_url/>
          </ht:news_item>
          <ht:news_item>
            <ht:news_item_title>   </ht:news_item_title>
            <ht:news_item_url>   </ht:news_item_url>
            <ht:news_item_source>   </ht:news_item_source>
          </ht:news_item>
          <ht:news_item>
            <ht:news_item_title>  기사 D  </ht:news_item_title>
            <ht:news_item_url>  https://example.test/news/4  </ht:news_item_url>
            <ht:news_item_source>  가상 매체  </ht:news_item_source>
          </ht:news_item>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == ()
    assert len(result.candidates) == 1

    sources = result.candidates[0].source_candidates

    assert sources == (
        ParsedSource(
            item_news_index=0,
            raw_title=None,
            raw_url="https://example.test/news/1",
            publisher_name=None,
        ),
        ParsedSource(
            item_news_index=1,
            raw_title="기사 B",
            raw_url=None,
            publisher_name=None,
        ),
        ParsedSource(
            item_news_index=2,
            raw_title=None,
            raw_url=None,
            publisher_name=None,
        ),
        ParsedSource(
            item_news_index=3,
            raw_title="  기사 D  ",
            raw_url="  https://example.test/news/4  ",
            publisher_name="  가상 매체  ",
        ),
    )

# ---------------------------------------------------------------------
# P-05: 발행일 시간대 보존 및 잘못된 날짜 경고
# ---------------------------------------------------------------------

def test_p05_parses_timezone_aware_pub_date() -> None:
    """RFC 822 날짜의 원래 시간대 오프셋을 유지한다."""
    xml_bytes = """<rss version="2.0">
      <channel>
        <item>
          <title>가상 기술 발표</title>
          <pubDate>Fri, 30 Oct 2026 10:00:00 -0700</pubDate>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)
    candidate = result.candidates[0]

    expected_date = datetime(
        2026,
        10,
        30,
        10,
        0,
        tzinfo=timezone(-timedelta(hours=7)),
    )

    assert candidate.rss_published_at == expected_date

    published_at = candidate.rss_published_at

    assert published_at is not None
    assert published_at == expected_date
    assert published_at.utcoffset() == -timedelta(hours=7)
    assert candidate.warnings == ()


@pytest.mark.parametrize(
    "pub_date",
    [
        "not-a-date",
        "Fri, 30 Oct 2026 10:00:00",
        " ",
    ],
)
def test_p05_invalid_pub_date_adds_warning(pub_date: str) -> None:
    """유효하지 않은 발행일은 후보를 유지하고 Warning으로 기록한다."""
    xml_bytes = f"""<rss version="2.0">
      <channel>
        <item>
          <title>가상 기술 발표</title>
          <pubDate>{pub_date}</pubDate>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)
    candidate = result.candidates[0]

    assert candidate.rss_published_at is None
    assert candidate.warnings == (WarningCode.INVALID_PUB_DATE,)
    assert result.item_issues == ()

# ---------------------------------------------------------------------
# P-06: XML 문법 및 RSS 구조 오류 검증
# ---------------------------------------------------------------------

def test_p06_malformed_xml_has_explicit_error_code() -> None:
    """잘못된 XML은 INVALID_XML로 전체 실패한다."""
    fixture = Path(__file__).parent / "fixtures" / "malformed_feed.xml"

    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(fixture.read_bytes())

    assert exc_info.value.code == FeedParseErrorCode.INVALID_XML


@pytest.mark.parametrize(
    "xml_bytes",
    [
        b"<feed version='2.0'><channel /></feed>",
        b"<rss><channel /></rss>",
        b"<rss version='1.0'><channel /></rss>",
        b"<rss version='2.0'><item /></rss>",
    ],
)
def test_p06_rejects_unsupported_feed_structure(
    xml_bytes: bytes,
) -> None:
    """루트·버전·Channel 구조 오류를 일관되게 반환한다."""
    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(xml_bytes)

    assert (
        exc_info.value.code
        == FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
    )

# ---------------------------------------------------------------------
# P-07: 정상·오류 Item 혼합 시 부분 실패 보존
# ---------------------------------------------------------------------

def test_p07_mixed_items_preserve_candidates_and_issues() -> None:
    """정상·오류 Item이 혼합되어도 원본 위치와 부분 실패를 보존한다."""
    fixture = Path(__file__).parent / "fixtures" / "missing_fields.xml"

    result = parse_rss_feed(fixture.read_bytes())

    assert result.item_issues == (
        ItemIssue(item_index=1, code=ItemIssueCode.MISSING_ITEM_TITLE),
        ItemIssue(item_index=3, code=ItemIssueCode.MISSING_ITEM_TITLE),
    )

    assert [
        (candidate.item_index, candidate.raw_title)
        for candidate in result.candidates
    ] == [
        (0, "가상 로봇 발표"),
        (2, "  가상 AI 행사  "),
        (4, "가상 게임 박람회"),
    ]

    assert [candidate.warnings for candidate in result.candidates] == [
        (),
        (WarningCode.INVALID_PUB_DATE,),
        (),
    ]

    ai_candidate = result.candidates[1]

    assert ai_candidate.rss_published_at is None
    assert ai_candidate.source_candidates == (
        ParsedSource(
            item_news_index=0,
            raw_title=None,
            raw_url="https://example.test/ai/1",
            publisher_name=None,
        ),
        ParsedSource(
            item_news_index=1,
            raw_title="기사 제목만 존재",
            raw_url=None,
            publisher_name=None,
        ),
    )

    assert len(result.candidates[0].source_candidates) == 1
    assert result.candidates[2].source_candidates == ()

# ---------------------------------------------------------------------
# P-08: DTD·Entity·외부 참조 보안 차단
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "xml_bytes",
    [
        pytest.param(
            b'<!DOCTYPE rss>'
            b'<rss version="2.0"><channel /></rss>',
            id="dtd",
        ),
        pytest.param(
            b'<!DOCTYPE rss [<!ENTITY sample "fictional">]>'
            b'<rss version="2.0"><channel><item>'
            b'<title>&sample;</title></item></channel></rss>',
            id="internal-entity",
        ),
        pytest.param(
            b'<!DOCTYPE rss ['
            b'<!ENTITY sample SYSTEM "file:///synthetic-do-not-read">'
            b']><rss version="2.0"><channel><item>'
            b'<title>&sample;</title></item></channel></rss>',
            id="external-file",
        ),
        pytest.param(
            b'<!DOCTYPE rss ['
            b'<!ENTITY sample SYSTEM "https://example.invalid/rss-test">'
            b']><rss version="2.0"><channel><item>'
            b'<title>&sample;</title></item></channel></rss>',
            id="external-url",
        ),
    ],
)
def test_p08_rejects_xml_security_constructs(
    xml_bytes: bytes,
) -> None:
    """DTD·Entity·외부 참조는 명시적인 보안 오류로 거부한다."""
    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(xml_bytes)

    assert (
        exc_info.value.code
        == FeedParseErrorCode.XML_SECURITY_REJECTED
    )
    assert str(exc_info.value) == "XML_SECURITY_REJECTED"


def test_p08_passes_all_defusedxml_security_options() -> None:
    """DTD, Entity, External 참조 방어 옵션이 모두 전달된다."""
    xml_bytes = b'<rss version="2.0"><channel /></rss>'
    original_fromstring = rss_parser.fromstring

    with patch.object(
        rss_parser, "fromstring", wraps=original_fromstring
    ) as parse_spy:
        result = rss_parser.parse_rss_feed(xml_bytes)

    assert result.candidates == ()
    assert result.item_issues == ()

    parse_spy.assert_called_once_with(
        xml_bytes,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )

# ---------------------------------------------------------------------
# P-09: RSS XML 자원 상한 검증
# ---------------------------------------------------------------------

P09_MAX_XML_BYTES = 2_097_152


def _p09_feed(item_xml: str) -> bytes:
    """외부 요청 없이 합성 RSS XML을 만든다."""
    return (
        '<rss version="2.0" '
        'xmlns:ht="https://trends.google.com/trending/rss">'
        f"<channel>{item_xml}</channel></rss>"
    ).encode("utf-8")


def _p09_assert_error(
    xml_bytes: bytes,
    expected_code: FeedParseErrorCode,
) -> None:
    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(xml_bytes)

    assert exc_info.value.code == expected_code


def _p09_nested_item(depth: int) -> str:
    """rss=1, channel=2, item=3 기준으로 깊이를 구성한다."""
    nested_count = depth - 3

    return (
        "<item><title>가상 깊이 검사</title>"
        + "<extra>" * nested_count
        + "</extra>" * nested_count
        + "</item>"
    )


def test_p09_accepts_exact_xml_byte_limit() -> None:
    """XML 입력이 정확히 2MiB이면 허용한다."""
    base = _p09_feed("<item><title>가상 기술</title></item>")
    xml_bytes = base + b" " * (P09_MAX_XML_BYTES - len(base))

    assert len(xml_bytes) == P09_MAX_XML_BYTES

    result = parse_rss_feed(xml_bytes)

    assert len(result.candidates) == 1
    assert result.candidates[0].raw_title == "가상 기술"


def test_p09_rejects_xml_byte_limit_exceeded() -> None:
    """입력이 2MiB를 1바이트라도 초과하면 전체 거부한다."""
    base = _p09_feed("<item><title>가상 기술</title></item>")
    xml_bytes = base + b" " * (P09_MAX_XML_BYTES + 1 - len(base))

    _p09_assert_error(
        xml_bytes,
        FeedParseErrorCode.INPUT_TOO_LARGE,
    )


def test_p09_accepts_exact_item_limit() -> None:
    """Item 200개는 허용하며 순서를 유지한다."""
    item_xml = "<item><title>가상 기술</title></item>" * 200

    result = parse_rss_feed(_p09_feed(item_xml))

    assert len(result.candidates) == 200
    assert result.item_issues == ()
    assert [item.item_index for item in result.candidates] == list(range(200))


def test_p09_rejects_item_limit_exceeded() -> None:
    """Item 201개는 전체 거부한다."""
    item_xml = "<item><title>가상 기술</title></item>" * 201

    _p09_assert_error(
        _p09_feed(item_xml),
        FeedParseErrorCode.TOO_MANY_ITEMS,
    )


def test_p09_accepts_exact_news_item_limit() -> None:
    """Item 내부 기사 20개는 모두 유지한다."""
    item_xml = (
        "<item><title>가상 기술</title>"
        + "<ht:news_item/>" * 20
        + "</item>"
    )

    result = parse_rss_feed(_p09_feed(item_xml))

    sources = result.candidates[0].source_candidates

    assert len(sources) == 20
    assert [source.item_news_index for source in sources] == list(range(20))


def test_p09_rejects_news_item_limit_exceeded() -> None:
    """Item 내부 기사 21개는 전체 거부한다."""
    item_xml = (
        "<item><title>가상 기술</title>"
        + "<ht:news_item/>" * 21
        + "</item>"
    )

    _p09_assert_error(
        _p09_feed(item_xml),
        FeedParseErrorCode.TOO_MANY_NEWS_ITEMS,
    )


def test_p09_accepts_exact_xml_depth_limit() -> None:
    """XML 최대 깊이 32는 허용한다."""
    xml_bytes = _p09_feed(_p09_nested_item(32))

    result = parse_rss_feed(xml_bytes)

    assert len(result.candidates) == 1


def test_p09_rejects_xml_depth_limit_exceeded() -> None:
    """XML 깊이 33은 전체 거부한다."""
    xml_bytes = _p09_feed(_p09_nested_item(33))

    _p09_assert_error(
        xml_bytes,
        FeedParseErrorCode.XML_DEPTH_LIMIT,
    )


def test_p09_checks_news_limit_before_discarding_invalid_item() -> None:
    """제목이 없는 Item도 기사 수 상한을 먼저 검사한다."""
    item_xml = "<item>" + "<ht:news_item/>" * 21 + "</item>"

    _p09_assert_error(
        _p09_feed(item_xml),
        FeedParseErrorCode.TOO_MANY_NEWS_ITEMS,
    )



# ---------------------------------------------------------------------
# P-10: XML 구조 경계 검증
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_news_xml",
    [
        pytest.param(
            "<other:news_item/>",
            id="unexpected-namespace-uri",
        ),
        pytest.param(
            "<news_item/>",
            id="missing-namespace",
        ),
    ],
)
def test_p10_rejects_unrecognized_news_item_namespace(
    invalid_news_xml: str,
) -> None:
    """news_item의 Namespace가 다르면 조용히 무시하지 않는다."""
    xml_bytes = f"""<rss version="2.0"
      xmlns:ht="https://trends.google.com/trending/rss"
      xmlns:other="urn:fictional:other">
      <channel>
        <item>
          <title>가상 기술 발표</title>
          <ht:news_item/>
          {invalid_news_xml}
        </item>
      </channel>
    </rss>""".encode("utf-8")

    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(xml_bytes)

    assert (
        exc_info.value.code
        == FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
    )


def test_p10_ignores_items_outside_direct_channel_children() -> None:
    """중첩 Item을 수집하거나 직접 자식 Item의 순서를 바꾸지 않는다."""
    xml_bytes = """<rss version="2.0">
      <channel>
        <item>
          <title>가상 기술 A</title>
          <extra>
            <item><title>중첩된 가상 기술</title></item>
          </extra>
        </item>
        <group>
          <item><title>그룹 안의 가상 기술</title></item>
        </group>
        <item>
          <title>가상 기술 B</title>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == ()
    assert [
        (candidate.item_index, candidate.raw_title)
        for candidate in result.candidates
    ] == [
        (0, "가상 기술 A"),
        (1, "가상 기술 B"),
    ]


def test_p10_rejects_multiple_channels() -> None:
    """Channel이 두 개면 첫 번째만 선택하지 않고 전체 거부한다."""
    xml_bytes = """<rss version="2.0">
      <channel>
        <item><title>첫 번째 채널</title></item>
      </channel>
      <channel>
        <item><title>두 번째 채널</title></item>
      </channel>
    </rss>""".encode("utf-8")

    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(xml_bytes)

    assert (
        exc_info.value.code
        == FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
    )


def test_p10_allows_unrecognized_optional_elements() -> None:
    """news_item이 아닌 미지의 선택적 확장 태그는 허용한다."""
    xml_bytes = """<rss version="2.0"
      xmlns:ht="https://trends.google.com/trending/rss"
      xmlns:other="urn:fictional:other">
      <channel>
        <other:optional_channel_field>가상 값</other:optional_channel_field>
        <item>
          <title>가상 기술 행사</title>
          <other:optional_item_field>임의 정보</other:optional_item_field>
          <ht:news_item>
            <ht:news_item_title>가상 기사</ht:news_item_title>
            <other:optional_source_field/>
          </ht:news_item>
        </item>
      </channel>
    </rss>""".encode("utf-8")

    result = parse_rss_feed(xml_bytes)

    assert result.item_issues == ()
    assert len(result.candidates) == 1

    sources = result.candidates[0].source_candidates

    assert len(sources) == 1
    assert sources[0].raw_title == "가상 기사"
    assert sources[0].raw_url is None



# ---------------------------------------------------------------------
# P-11: 입력 타입 및 빈 bytes 검증
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_input",
    [
        pytest.param(None, id="none"),
        pytest.param(
            "<rss version='2.0'><channel /></rss>",
            id="str",
        ),
        pytest.param(
            bytearray(b"<rss version='2.0'><channel /></rss>"),
            id="bytearray",
        ),
        pytest.param(
            memoryview(b"<rss version='2.0'><channel /></rss>"),
            id="memoryview",
        ),
        pytest.param(
            Path("fictional-feed.xml"),
            id="path",
        ),
        pytest.param(123, id="integer"),
    ],
)
def test_p11_rejects_non_bytes_input(
    invalid_input: object,
) -> None:
    """bytes가 아닌 입력은 자동 변환 없이 명시적으로 거부한다."""
    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(cast(bytes, invalid_input))

    assert (
        exc_info.value.code
        == FeedParseErrorCode.INVALID_INPUT_TYPE
    )


def test_p11_rejects_empty_bytes() -> None:
    """빈 bytes는 INVALID_XML이 아니라 EMPTY_INPUT으로 구분한다."""
    with pytest.raises(FeedParseError) as exc_info:
        parse_rss_feed(b"")

    assert exc_info.value.code == FeedParseErrorCode.EMPTY_INPUT
