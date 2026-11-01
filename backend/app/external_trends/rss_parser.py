"""RSS 2.0의 XML 바이트를 독립된 후보 데이터로 해석한다."""

from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element, ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

from app.external_trends.errors import FeedParseError, FeedParseErrorCode
from app.external_trends.types import (
    ItemIssue,
    ItemIssueCode,
    ParsedCandidate,
    ParsedFeed,
    ParsedSource,
    WarningCode,
)

HT_NAMESPACE = "https://trends.google.com/trending/rss"
NEWS_ITEM_TAG = f"{{{HT_NAMESPACE}}}news_item"
MAX_XML_BYTES = 2_097_152
MAX_ITEMS = 200
MAX_NEWS_ITEMS_PER_ITEM = 20
MAX_XML_DEPTH = 32

def _optional_text(element, tag: str) -> str | None:
    """빈 값만 None으로 바꾸고, 나머지 원문은 P2에 전달한다."""
    raw = element.findtext(tag)
    return None if raw is None or not raw.strip() else raw



def _parse_pub_date(
    item,
) -> tuple[datetime | None, tuple[WarningCode, ...]]:
    """RSS 발행일을 timezone-aware datetime으로 해석한다."""
    date_element = item.find("pubDate")

    if date_element is None:
        return None, ()

    raw_date = date_element.text

    if raw_date is None or not raw_date.strip():
        return None, (WarningCode.INVALID_PUB_DATE,)

    try:
        parsed_date = parsedate_to_datetime(raw_date.strip())
    except (TypeError, ValueError):
        return None, (WarningCode.INVALID_PUB_DATE,)

    if parsed_date.utcoffset() is None:
        return None, (WarningCode.INVALID_PUB_DATE,)

    return parsed_date, ()

def _enforce_resource_limits(
    root: Element,
    channel: Element,
) -> list[Element]:
    """XML 전체 깊이와 직접 자식 Item·기사 개수를 검증한다."""

    # 재귀 호출 없이 모든 XML 요소의 깊이를 검사한다.
    pending: list[tuple[Element, int]] = [(root, 1)]

    while pending:
        element, depth = pending.pop()

        if depth > MAX_XML_DEPTH:
            raise FeedParseError(
                FeedParseErrorCode.XML_DEPTH_LIMIT
            )

        for child in element:
            pending.append((child, depth + 1))

    # channel의 직접 자식 Item만 대상으로 한다.
    items = channel.findall("item")

    if len(items) > MAX_ITEMS:
        raise FeedParseError(
            FeedParseErrorCode.TOO_MANY_ITEMS
        )

    # 정상 제목 여부와 무관하게 모든 Item을 검사한다.
    for item in items:
        news_items = item.findall(NEWS_ITEM_TAG)

        if len(news_items) > MAX_NEWS_ITEMS_PER_ITEM:
            raise FeedParseError(
                FeedParseErrorCode.TOO_MANY_NEWS_ITEMS
            )

    return items


def _validate_news_item_namespaces(root: Element) -> None:
    """news_item과 같은 이름의 미지원 Namespace를 거부한다."""
    for element in root.iter():
        tag = element.tag

        if not isinstance(tag, str):
            continue

        local_name = tag.rsplit("}", 1)[-1]

        if local_name == "news_item" and tag != NEWS_ITEM_TAG:
            raise FeedParseError(
                FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
            )



def parse_rss_feed(xml_bytes: bytes) -> ParsedFeed:
    if not isinstance(xml_bytes, bytes):
        raise FeedParseError(
            FeedParseErrorCode.INVALID_INPUT_TYPE
        )

    if not xml_bytes:
        raise FeedParseError(
            FeedParseErrorCode.EMPTY_INPUT
        )

    if len(xml_bytes) > MAX_XML_BYTES:
        raise FeedParseError(
            FeedParseErrorCode.INPUT_TOO_LARGE
        )

    try:
        root = fromstring(
            xml_bytes,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except DefusedXmlException:
        raise FeedParseError(
            FeedParseErrorCode.XML_SECURITY_REJECTED
        ) from None
    except ParseError as exc:
        raise FeedParseError(FeedParseErrorCode.INVALID_XML) from exc

    if root.tag != "rss" or root.get("version") != "2.0":
        raise FeedParseError(
            FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
        )

    channels = root.findall("channel")

    if len(channels) != 1:
        raise FeedParseError(
            FeedParseErrorCode.UNSUPPORTED_FEED_STRUCTURE
        )

    channel = channels[0]

    items = _enforce_resource_limits(root, channel)
    _validate_news_item_namespaces(root)

    candidates = []
    item_issues: list[ItemIssue] = []

    for item_index, item in enumerate(items):
        raw_title = _optional_text(item, "title")

        if raw_title is None:
            item_issues.append(
                ItemIssue(
                    item_index=item_index,
                    code=ItemIssueCode.MISSING_ITEM_TITLE,
                )
            )
            continue

        sources = []

        for news_index, news_item in enumerate(
            item.findall(NEWS_ITEM_TAG)
        ):
            sources.append(
                ParsedSource(
                    item_news_index=news_index,
                    raw_title=_optional_text(
                        news_item,
                        f"{{{HT_NAMESPACE}}}news_item_title",
                    ),
                    raw_url=_optional_text(
                        news_item,
                        f"{{{HT_NAMESPACE}}}news_item_url",
                    ),
                    publisher_name=_optional_text(
                        news_item,
                        f"{{{HT_NAMESPACE}}}news_item_source",
                    ),
                )
            )

        published_at, warnings = _parse_pub_date(item)

        candidates.append(
            ParsedCandidate(
                item_index=item_index,
                raw_title=raw_title,
                rss_published_at=published_at,
                source_candidates=tuple(sources),
                warnings=warnings,
            )
        )

    return ParsedFeed(
        candidates=tuple(candidates),
        item_issues=tuple(item_issues),
    )
