"""Gate D0의 순수 오프라인 설정 검증·계획. 요청 실행 권한을 부여하지 않는다."""

from dataclasses import dataclass, field, fields
from datetime import date, datetime, timedelta, timezone
from typing import Literal

# 현재 실행일의 서울 표준시. 과거 DST/역사 시각 변환용 IANA 구현이 아니다.
_SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


class GateDPreflightError(Exception):
    """입력 원문이나 비밀값을 담지 않는 사전 검증 실패."""

    code: Literal["INVALID_CONFIGURATION"] = "INVALID_CONFIGURATION"

    def __init__(self) -> None:
        super().__init__("D0 preflight configuration invalid")


@dataclass(frozen=True, slots=True)
class GateDConfig:
    model: str = "gpt-6-luna"
    profile: str = "IT_DIGITAL"
    lookback_days: int = 7
    max_candidates: int = 3
    timeout: float = 60.0
    max_output_tokens: int = 4096
    max_tool_calls: int = 1
    max_retries: int = 0
    store: bool = False
    stream: bool = False

    def __post_init__(self) -> None:
        for setting in fields(self):
            value = getattr(self, setting.name)
            # Equality alone would accept True == 1 or 4096.0 == 4096.
            if type(value) is not type(setting.default) or value != setting.default:
                raise GateDPreflightError()


@dataclass(frozen=True, slots=True)
class GateDPreflightPlan:
    config: GateDConfig
    start_date: date
    end_date: date
    input_text: str
    status: Literal["PREFLIGHT_VALIDATED"] = field(
        default="PREFLIGHT_VALIDATED", init=False,
    )
    live_request_allowed: Literal[False] = field(default=False, init=False)
    timezone: Literal["Asia/Seoul"] = field(default="Asia/Seoul", init=False)


def build_preflight_plan(
    *, config: GateDConfig = GateDConfig(), execution_at: datetime | None = None,
) -> GateDPreflightPlan:
    """현재 또는 명시된 aware 시각으로 계획만 생성한다. I/O는 수행하지 않는다."""
    if type(config) is not GateDConfig:
        raise GateDPreflightError()
    config.__post_init__()
    instant = datetime.now(timezone.utc) if execution_at is None else execution_at
    if not isinstance(instant, datetime):
        raise GateDPreflightError()
    try:
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise GateDPreflightError()
        end = instant.astimezone(_SEOUL).date()
        start = end - timedelta(days=config.lookback_days - 1)
    except (ValueError, OverflowError):
        raise GateDPreflightError() from None
    input_text = (
        f"{start.isoformat()}~{end.isoformat()} (Asia/Seoul, 양 끝 날짜 포함) "
        "대한민국 관련 IT/디지털 기술 주제 후보를 최대 3건 찾아주세요."
        ' 출력은 {"candidates":[{"topic_draft":"주제 초안",'
        '"source_url":"확인 가능한 출처 URL",'
        '"source_title_reference":"출처 제목 참고"}]} 형태의 JSON 객체로 작성하세요.'
        " JSON 본문만 반환하고 설명문이나 Markdown 코드 블록은 포함하지 마세요."
        " 각 후보의 source_url과 인용 URL을 동일하게 연결하여 검토 가능하게 하세요."
        " 근거 없는 인기도·랭킹·출처 게시일은 생성하지 마세요."
        ' 확인 가능한 후보가 없으면 {"candidates":[]}를 반환하세요.'
    )
    return GateDPreflightPlan(
        config=config, start_date=start, end_date=end, input_text=input_text,
    )
