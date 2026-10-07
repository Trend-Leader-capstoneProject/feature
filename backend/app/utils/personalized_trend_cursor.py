import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

PERSONALIZED_TREND_CURSOR_VERSION = 1

MAX_PERSONALIZED_TREND_CURSOR_LENGTH = 512

_CURSOR_KEYS = {
    "version",
    "last_collected_at",
    "trend_id",
    "context_fingerprint",
}

class PersonalizedTrendCursorError(ValueError):
    """맞춤 Trend 목록 Cursor를 해석할 수 없을 때 발생한다."""

@dataclass(
    frozen=True,
    slots=True,
)
class PersonalizedTrendCursor:
    """맞춤 Trend 목록의 다음 페이지 경계를 나타내는 Cursor 값."""

    last_collected_at: datetime
    trend_id: int
    context_fingerprint: str


def build_personalized_context_fingerprint(
    *,
    user_id: int,
    effective_child_category_ids: list[int],
) -> str:
    """현재 사용자와 유효 Child Category 집합의 Fingerprint를 생성한다."""

    normalized_category_ids = sorted(
        set(
            effective_child_category_ids,
        )
    )

    serialized_context = (
        f"user:{user_id}|categories:"
        + ",".join(
            str(category_id)
            for category_id
            in normalized_category_ids
        )
    )

    return hashlib.sha256(
        serialized_context.encode(
            "utf-8",
        )
    ).hexdigest()


def encode_personalized_trend_cursor(
    cursor: PersonalizedTrendCursor,
) -> str:
    """PersonalizedTrendCursor를 URL-safe opaque 문자열로 변환한다."""

    payload = {
        "version": PERSONALIZED_TREND_CURSOR_VERSION,
        "last_collected_at": (
            cursor.last_collected_at.isoformat(
                timespec="microseconds",
            )
        ),
        "trend_id": cursor.trend_id,
        "context_fingerprint": (
            cursor.context_fingerprint
        ),
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


def decode_personalized_trend_cursor(
    cursor: str,
) -> PersonalizedTrendCursor:
    """URL-safe Cursor 문자열을 검증하고 PersonalizedTrendCursor로 변환한다."""

    if (
        not isinstance(cursor, str)
        or not cursor
        or cursor != cursor.strip()
        or len(cursor) > MAX_PERSONALIZED_TREND_CURSOR_LENGTH
    ):
        raise PersonalizedTrendCursorError(
            "Cursor 형식이 올바르지 않습니다.",
        )

    payload = _decode_payload(
        cursor,
    )

    if (
        not isinstance(payload, dict)
        or set(payload) != _CURSOR_KEYS
    ):
        raise PersonalizedTrendCursorError(
            "Cursor payload가 올바르지 않습니다.",
        )

    version = payload["version"]

    if (
        type(version) is not int
        or version != PERSONALIZED_TREND_CURSOR_VERSION
    ):
        raise PersonalizedTrendCursorError(
            "지원하지 않는 Cursor 버전입니다.",
        )

    return PersonalizedTrendCursor(
        last_collected_at=datetime.fromisoformat(
            payload["last_collected_at"],
        ),
        trend_id=payload["trend_id"],
        context_fingerprint=(
            payload["context_fingerprint"]
        ),
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
        raise PersonalizedTrendCursorError(
            "Cursor 형식이 올바르지 않습니다.",
        ) from exc
