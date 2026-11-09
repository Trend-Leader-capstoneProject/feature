"""RSS Parser의 명시적인 오류 계약."""

from enum import StrEnum


class FeedParseErrorCode(StrEnum):
    INVALID_INPUT_TYPE = "INVALID_INPUT_TYPE"
    EMPTY_INPUT = "EMPTY_INPUT"
    INVALID_XML = "INVALID_XML"
    UNSUPPORTED_FEED_STRUCTURE = "UNSUPPORTED_FEED_STRUCTURE"
    XML_SECURITY_REJECTED = "XML_SECURITY_REJECTED"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    TOO_MANY_ITEMS = "TOO_MANY_ITEMS"
    TOO_MANY_NEWS_ITEMS = "TOO_MANY_NEWS_ITEMS"
    XML_DEPTH_LIMIT = "XML_DEPTH_LIMIT"


class FeedParseError(ValueError):
    """RSS 피드 전체의 파싱 실패를 나타낸다."""

    def __init__(self, code: FeedParseErrorCode) -> None:
        self.code = code
        super().__init__(code.value)
