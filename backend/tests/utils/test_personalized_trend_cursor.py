import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.utils.personalized_trend_cursor import (
    MAX_PERSONALIZED_TREND_CURSOR_LENGTH,
    PersonalizedTrendCursor,
    PersonalizedTrendCursorError,
    build_personalized_context_fingerprint,
    decode_personalized_trend_cursor,
    encode_personalized_trend_cursor,
)
from app.utils.trend_cursor import (
    TrendCursor,
    encode_trend_cursor,
)


def test_personalized_context_fingerprint_is_stable_for_same_child_set() -> None:
    """Child ID의 순서와 중복이 달라도 같은 Context는 같은 Fingerprint다."""

    first = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            5,
            3,
            5,
            8,
        ],
    )

    second = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            8,
            5,
            3,
        ],
    )

    assert first == second


def test_personalized_context_fingerprint_changes_for_different_user() -> None:
    """Child Scope가 같아도 인증 사용자가 다르면 다른 Context다."""

    first = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            3,
            5,
            8,
        ],
    )

    second = build_personalized_context_fingerprint(
        user_id=16,
        effective_child_category_ids=[
            3,
            5,
            8,
        ],
    )

    assert first != second


def test_personalized_context_fingerprint_changes_for_different_child_set() -> None:
    """인증 사용자가 같아도 Effective Child 집합이 다르면 Context가 다르다."""

    first = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            3,
            5,
            8,
        ],
    )

    second = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            3,
            5,
            9,
        ],
    )

    assert first != second


def test_personalized_context_fingerprint_uses_canonical_sha256() -> None:
    """정규화된 Context를 고정 형식으로 직렬화해 SHA-256을 사용한다."""

    fingerprint = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[
            8,
            3,
            5,
            3,
        ],
    )

    assert fingerprint == (
        "0cad623bda0a0623eb9317dd08eda4255"
        "d647145cc40aefd07f8dfea9c5646b8"
    )


def test_personalized_trend_cursor_round_trip() -> None:
    """맞춤 Cursor는 정렬 경계와 관심사 Context를 보존한다."""

    cursor = PersonalizedTrendCursor(
        last_collected_at=datetime(
            2026,
            10,
            6,
            15,
            30,
            10,
            123456,
        ),
        trend_id=101,
        context_fingerprint=(
            "0cad623bda0a0623eb9317dd08eda4255"
            "d647145cc40aefd07f8dfea9c5646b8"
        ),
    )

    encoded = encode_personalized_trend_cursor(
        cursor,
    )
    decoded = decode_personalized_trend_cursor(
        encoded,
    )

    assert decoded == cursor


def encode_raw_cursor(
    payload: dict[str, object],
) -> str:
    """비정상 Personalized Cursor payload 테스트용 raw encoder."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return base64.urlsafe_b64encode(
        serialized,
    ).decode("ascii").rstrip("=")


def make_valid_personalized_cursor_payload() -> dict[str, object]:
    """Personalized Cursor 검증 테스트용 정상 payload를 생성한다."""

    return {
        "version": 1,
        "last_collected_at": (
            "2026-10-06T15:30:10.123456"
        ),
        "trend_id": 101,
        "context_fingerprint": (
            "0cad623bda0a0623eb9317dd08eda4255"
            "d647145cc40aefd07f8dfea9c5646b8"
        ),
    }


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        " ",
        "not-a-valid-cursor!",
    ],
)
def test_decode_personalized_trend_cursor_rejects_invalid_encoded_value(
    cursor: str,
) -> None:
    """빈 값 또는 올바르지 않은 인코딩은 유효한 Cursor가 아니다."""

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )

def test_decode_personalized_trend_cursor_rejects_unsupported_version() -> None:
    """지원하지 않는 Personalized Cursor version은 거부한다."""

    payload = make_valid_personalized_cursor_payload()
    payload["version"] = 2

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


def test_decode_personalized_trend_cursor_rejects_missing_field() -> None:
    """필수 Personalized Cursor 필드가 누락되면 거부한다."""

    payload = make_valid_personalized_cursor_payload()
    payload.pop(
        "trend_id",
    )

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


def test_decode_personalized_trend_cursor_rejects_unknown_field() -> None:
    """정의되지 않은 Personalized Cursor 필드가 추가되면 거부한다."""

    payload = make_valid_personalized_cursor_payload()
    payload["unexpected"] = "value"

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        0,
        True,
    ],
)
def test_decode_personalized_trend_cursor_rejects_invalid_trend_id(
    invalid_value: object,
) -> None:
    """trend_id는 bool이 아닌 양의 정수여야 한다."""

    payload = make_valid_personalized_cursor_payload()
    payload["trend_id"] = invalid_value

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


def test_decode_personalized_trend_cursor_rejects_noncanonical_datetime() -> None:
    """발급 형식과 다른 datetime 정밀도는 거부한다."""

    payload = make_valid_personalized_cursor_payload()
    payload["last_collected_at"] = (
        "2026-10-06T15:30:10"
    )

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [
        "abc",
        (
            "0CAD623BDA0A0623EB9317DD08EDA4255"
            "D647145CC40AEFD07F8DFEA9C5646B8"
        ),
        (
            "zcad623bda0a0623eb9317dd08eda4255"
            "d647145cc40aefd07f8dfea9c5646b8"
        ),
    ],
)
def test_decode_personalized_trend_cursor_rejects_invalid_fingerprint(
    invalid_value: str,
) -> None:
    """Context Fingerprint는 lowercase SHA-256 hex여야 한다."""

    payload = make_valid_personalized_cursor_payload()
    payload["context_fingerprint"] = invalid_value

    cursor = encode_raw_cursor(
        payload,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            cursor,
        )


def test_decode_personalized_trend_cursor_rejects_public_cursor() -> None:
    """Public Trend Cursor를 Personalized Cursor로 사용할 수 없다."""

    public_cursor = TrendCursor(
        last_collected_at=datetime(
            2026,
            10,
            6,
            15,
            30,
            10,
            123456,
        ),
        trend_id=101,
        category_id=None,
    )

    encoded = encode_trend_cursor(
        public_cursor,
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            encoded,
        )


def test_decode_personalized_trend_cursor_rejects_oversized_value() -> None:
    """최대 허용 길이를 넘는 Cursor는 decode 전에 거부한다."""

    oversized_cursor = (
        "a"
        * (
            MAX_PERSONALIZED_TREND_CURSOR_LENGTH
            + 1
        )
    )

    with pytest.raises(
        PersonalizedTrendCursorError,
    ):
        decode_personalized_trend_cursor(
            oversized_cursor,
        )


def test_personalized_trend_cursor_preserves_timezone() -> None:
    """Cursor codec은 datetime timezone 정보를 임의 변환하지 않는다."""

    cursor = PersonalizedTrendCursor(
        last_collected_at=datetime(
            2026,
            10,
            6,
            15,
            30,
            10,
            123456,
            tzinfo=timezone(
                timedelta(hours=9),
            ),
        ),
        trend_id=101,
        context_fingerprint=(
            "0cad623bda0a0623eb9317dd08eda4255"
            "d647145cc40aefd07f8dfea9c5646b8"
        ),
    )

    decoded = decode_personalized_trend_cursor(
        encode_personalized_trend_cursor(
            cursor,
        ),
    )

    assert decoded.last_collected_at == (
        cursor.last_collected_at
    )
    assert decoded.last_collected_at.utcoffset() == (
        timedelta(hours=9)
    )
