import base64
import json
from datetime import datetime

import pytest

from app.utils.personalized_trend_cursor import (
    PersonalizedTrendCursor,
    PersonalizedTrendCursorError,
    build_personalized_context_fingerprint,
    decode_personalized_trend_cursor,
    encode_personalized_trend_cursor,
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
