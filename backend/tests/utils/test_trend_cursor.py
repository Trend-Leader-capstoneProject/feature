import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.utils.trend_cursor import (
    TrendCursor,
    TrendCursorError,
    decode_trend_cursor,
    encode_trend_cursor,
)


def test_trend_cursor_round_trip_without_category() -> None:
    """필터 없는 Cursor는 정렬 경계와 null 필터 문맥을 보존한다."""

    cursor = TrendCursor(
        last_collected_at=datetime(
            2026,
            9,
            26,
            15,
            30,
            10,
            123456,
        ),
        trend_id=101,
        category_id=None,
    )

    encoded = encode_trend_cursor(cursor)
    decoded = decode_trend_cursor(encoded)

    assert decoded == cursor


def test_trend_cursor_round_trip_with_category() -> None:
    """Category 필터 Cursor는 요청 Category 문맥을 함께 보존한다."""

    cursor = TrendCursor(
        last_collected_at=datetime(
            2026,
            9,
            26,
            15,
            30,
            10,
            654321,
        ),
        trend_id=55,
        category_id=12,
    )

    encoded = encode_trend_cursor(cursor)
    decoded = decode_trend_cursor(encoded)

    assert decoded == cursor


def test_trend_cursor_does_not_assume_utc_or_kst() -> None:
    """Cursor codec은 datetime의 timezone 정보를 임의 변환하지 않는다."""

    cursor = TrendCursor(
        last_collected_at=datetime(
            2026,
            9,
            26,
            15,
            30,
            10,
            123456,
            tzinfo=timezone(
                timedelta(hours=9),
            ),
        ),
        trend_id=101,
        category_id=None,
    )

    decoded = decode_trend_cursor(
        encode_trend_cursor(cursor),
    )

    assert decoded.last_collected_at == (
        cursor.last_collected_at
    )
    assert decoded.last_collected_at.utcoffset() == (
        timedelta(hours=9)
    )


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        " ",
        "not-a-valid-cursor!",
    ],
)
def test_decode_trend_cursor_rejects_invalid_encoded_value(
    cursor: str,
) -> None:
    """빈 값 또는 올바르지 않은 인코딩은 유효한 Cursor가 아니다."""

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(cursor)


def encode_raw_cursur(
    payload: dict[str, object],
) -> str:
    """비정상 Cursor payload 테스트를 위한 raw encoder."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return base64.urlsafe_b64encode(
        serialized,
    ).decode("ascii").rstrip("=")


def make_valid_cursor_payload() -> dict[str, object]:
    """Cursor 검증 테스트용 정상 payload를 생성한다."""

    return {
        "version": 1,
        "last_collected_at": (
            "2026-09-26T12:00:00.123456"
        ),
        "trend_id": 101,
        "category_id": None,
    }

def test_decode_trend_cursor_rejects_unsupported_version() -> None:
    """지원하지 않는 Cursor version은 거부한다."""

    payload = make_valid_cursor_payload()
    payload["version"] = 2

    cursor = encode_raw_cursur(
        payload,
    )

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(
            cursor,
        )

def test_decode_trend_cursor_rejects_missing_field() -> None:
    """필수 Cursor 필드가 누락되면 거부한다."""

    payload = make_valid_cursor_payload()
    payload.pop(
        "trend_id",
    )

    cursor = encode_raw_cursur(
        payload,
    )

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(
            cursor,
        )

def test_decode_trend_cursor_rejects_unknown_field() -> None:
    """정의되지 않은 Cursor 필드가 추가되면 거부한다."""

    payload = make_valid_cursor_payload()
    payload["unexpected"] = "value"

    cursor = encode_raw_cursur(
        payload,
    )

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(
            cursor,
        )


@pytest.mark.parametrize(
     (
        "field_name",
        "invalid_value",
    ),
    [
        (
            "trend_id",
            0,
        ),
        (
            "trend_id",
            True,
        ),
        (
            "category_id",
            0,
        ),
        (
            "category_id",
            True,
        ),
    ],
)
def test_decode_trend_cursor_rejects_invalid_id(
    field_name: str,
    invalid_value: object,
) -> None:
    """Cursor ID는 bool이 아닌 양의 정수여야 한다."""

    payload = make_valid_cursor_payload()
    payload[field_name] = (
        invalid_value
    )

    cursor = encode_raw_cursur(
        payload,
    )

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(
            cursor,
        )

def test_decode_trend_cursor_rejects_noncanonical_datetime() -> None:
    """발급 형식과 다른 datetime 정밀도는 거부한다."""

    payload = make_valid_cursor_payload()
    payload["last_collected_at"] = (
        "2026-09-26T12:00:00"
    )

    cursor = encode_raw_cursur(
        payload,
    )

    with pytest.raises(
        TrendCursorError,
    ):
        decode_trend_cursor(
            cursor,
        )
