from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

TREND_CURSOR_VERSION = 1
MAX_TREND_CURSOR_LENGTH = 512
_CURSOR_KEYS = {
    "version",
    "last_collected_at",
    "trend_id",
    "category_id",
}


class TrendCursorError(ValueError):
    """Trend 목록 Cursor를 해석할 수 없을 때 발생한다."""

@dataclass(
    frozen=True,
    slots=True,
)
class TrendCursor:
    """Trend 목록의 다음 페이지 경계를 나타내는 Cursor 값."""

    last_collected_at: datetime
    trend_id: int
    category_id: int | None


def encode_trend_cursor(
    cursor: TrendCursor,
) -> str:
    """TrendCursor를 URL-safe opaque 문자열로 변환한다."""

    payload = {
        "version": TREND_CURSOR_VERSION,
        "last_collected_at": (
            cursor.last_collected_at.isoformat(
                timespec="microseconds",
            )
        ),
        "trend_id": cursor.trend_id,
        "category_id": cursor.category_id,
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    encoded = base64.urlsafe_b64encode(
        serialized,
    ).decode("ascii")

    return encoded.rstrip("=")

def decode_trend_cursor(
    cursor: str,
) -> TrendCursor:
    """URL-safe Cursor 문자열을 검증하고 TrendCursor로 변환한다."""

    if (
        not isinstance(cursor, str)
        or not cursor
        or cursor != cursor.strip()
        or len(cursor) > MAX_TREND_CURSOR_LENGTH
    ):
        raise TrendCursorError(
            "Cursor 형식이 올바르지 않습니다.",
        )

    payload = _decode_payload(cursor)

    if (
        not isinstance(payload, dict)
        or set(payload) != _CURSOR_KEYS
    ):
        raise TrendCursorError(
            "Cursor payload가 올바르지 않습니다.",
        )

    version = payload["version"]


    if (
        type(version) is not int
        or version != TREND_CURSOR_VERSION
    ):
        raise TrendCursorError(
            "지원하지 않는 Cursor 버전입니다.",
        )

    last_collected_at = _parse_datetime(
        payload["last_collected_at"],
    )

    trend_id = _parse_positive_int(
        payload["trend_id"],
        field_name="trend_id",
    )

    category_id_value = payload["category_id"]

    if category_id_value is None:
        category_id = None
    else:
        category_id = _parse_positive_int(
            category_id_value,
            field_name="category_id",
        )

    return TrendCursor(
        last_collected_at=last_collected_at,
        trend_id=trend_id,
        category_id=category_id,
    )


def _decode_payload(
    cursor: str,
) -> Any:
    """Base64 URL-safe 문자열을 JSON payload로 변환한다."""

    padding = "=" * (
        -len(cursor) % 4
    )

    try:
        decoded = base64.b64decode(
            (
                cursor
                + padding
            ).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )

        return json.loads(
            decoded.decode("utf-8"),
        )

    except (
        binascii.Error,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise TrendCursorError(
            "Cursor 형식이 올바르지 않습니다.",
        ) from exc


def _parse_datetime(
    value: Any,
) -> datetime:
    """Cursor datetime을 server 발급 형식 그대로 검증한다."""

    if not isinstance(value, str):
        raise TrendCursorError(
            "Cursor 시각 형식이 올바르지 않습니다.",
        )

    try:
        parsed = datetime.fromisoformat(
            value,
        )
    except ValueError as exc:
        raise TrendCursorError(
            "Cursor 시각 형식이 올바르지 않습니다.",
        ) from exc

    canonical = parsed.isoformat(
        timespec="microseconds",
    )

    if canonical != value:
        raise TrendCursorError(
            "Cursor 시각 정밀도가 올바르지 않습니다.",
        )

    return parsed


def _parse_positive_int(
    value: Any,
    *,
    field_name: str,
) -> int:
    """bool을 제외한 양의 정수 Cursor 필드를 검증한다."""

    if (
        type(value) is not int
        or value <= 0
    ):
        raise TrendCursorError(
            f"Cursor {field_name} 값이 올바르지 않습니다.",
        )

    return value
