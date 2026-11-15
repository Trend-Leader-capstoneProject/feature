"""DB는 UTC 초 단위 naive DATETIME, 외부 응답은 UTC aware 시각을 사용한다."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
