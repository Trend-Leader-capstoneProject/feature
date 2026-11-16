"""Explicit one-category exhibition plan and live boundary, independent of D0/S0."""

from dataclasses import dataclass, field, fields
from datetime import date, datetime, time, timedelta, timezone
from types import MappingProxyType
from typing import Literal

import httpx2

from . import d1_live_preview, gate_d_preflight

PROFILE_SCOPES = MappingProxyType({
    "FASHION": "패션 — 의류·신발·가방·주얼리·액세서리·패션 스타일",
    "BEAUTY": "뷰티 — 스킨케어·메이크업·헤어·향수·네일",
    "GAME": "게임 — 모바일·PC·콘솔 게임·e스포츠·게임 플랫폼·서비스",
    "FOOD": "음식 — 한식·중식·일식·양식·카페·디저트·식품·음료",
    "ENTERTAINMENT": "엔터테인먼트 — 음악·영화·드라마·예능·웹툰·애니메이션·연예인",
    "IT_DIGITAL": "IT/디지털 — 인공지능·모바일·PC·하드웨어·소프트웨어·플랫폼·서비스",
})


@dataclass(frozen=True, slots=True)
class DemoSearchConfig:
    profile: str
    model: str = "gpt-6-luna"
    lookback_days: int = 7
    max_candidates: int = 3
    timeout: float = 60.0
    max_output_tokens: int = 4096
    max_tool_calls: int = 1
    max_retries: int = 0
    store: bool = False
    stream: bool = False

    def __post_init__(self) -> None:
        if type(self.profile) is not str or self.profile not in PROFILE_SCOPES:
            raise ValueError("invalid demo search configuration")
        approved = gate_d_preflight.GateDConfig()
        for setting in fields(approved):
            if setting.name == "profile":
                continue
            value = getattr(self, setting.name)
            expected = getattr(approved, setting.name)
            if type(value) is not type(expected) or value != expected:
                raise ValueError("invalid demo search configuration")


@dataclass(frozen=True, slots=True)
class DemoSearchPlan:
    config: DemoSearchConfig
    start_date: date
    end_date: date
    input_text: str
    status: Literal["PREFLIGHT_VALIDATED"] = field(
        default="PREFLIGHT_VALIDATED", init=False,
    )
    live_request_allowed: Literal[False] = field(default=False, init=False)
    timezone: Literal["Asia/Seoul"] = field(default="Asia/Seoul", init=False)


def build_demo_plan(
    *, config: DemoSearchConfig, execution_at: datetime | None = None,
) -> DemoSearchPlan:
    """Build an offline plan; reuse D0's approved calendar without its profile."""
    if type(config) is not DemoSearchConfig:
        raise ValueError("invalid demo search configuration")
    config.__post_init__()
    try:
        calendar = gate_d_preflight.build_preflight_plan(execution_at=execution_at)
    except gate_d_preflight.GateDPreflightError:
        raise ValueError("invalid demo search configuration") from None
    input_text = (
        f"{calendar.start_date.isoformat()}~{calendar.end_date.isoformat()} "
        "(Asia/Seoul, 양 끝 날짜 포함) 대한민국 관련 "
        f"{config.profile} 분야({PROFILE_SCOPES[config.profile]})의 "
        "주제 후보를 최대 3건 찾아주세요."
        ' 출력은 {"candidates":[{"topic_draft":"주제 초안",'
        '"source_url":"확인 가능한 출처 URL",'
        '"source_title_reference":"출처 제목 참고"}]} 형태의 JSON 객체로 작성하세요.'
        " JSON 본문만 반환하고 설명문이나 Markdown 코드 블록은 포함하지 마세요."
        " 각 후보의 source_url과 인용 URL을 동일하게 연결하여 검토 가능하게 하세요."
        " 근거 없는 인기도·랭킹·출처 게시일은 생성하지 마세요."
        ' 확인 가능한 후보가 없으면 {"candidates":[]}를 반환하세요.'
    )
    return DemoSearchPlan(
        config=config, start_date=calendar.start_date, end_date=calendar.end_date,
        input_text=input_text,
    )


def valid_demo_plan(plan: object, *, synthetic: bool = False) -> bool:
    """Require exact regeneration; historical calendar anchors are Mock-only."""
    try:
        if (
            type(plan) is not DemoSearchPlan
            or type(plan.start_date) is not date or type(plan.end_date) is not date
            or type(plan.input_text) is not str
            or type(plan.status) is not str or type(plan.timezone) is not str
            or plan.live_request_allowed is not False
        ):
            return False
        anchor = (
            datetime.combine(plan.end_date, time(), timezone(timedelta(hours=9)))
            if synthetic else None
        )
        expected = build_demo_plan(config=plan.config, execution_at=anchor)
        return plan == expected
    except (AttributeError, ValueError, TypeError, OverflowError):
        return False


def run_demo_preview(
    *, plan: DemoSearchPlan, execute_live: bool = False,
    interactive: bool = False, confirmation: str | None = None,
    api_key: str | None = None, http_transport: httpx2.BaseTransport | None = None,
) -> dict[str, object]:
    """Validate the exhibition boundary before entering the shared D1 executor."""
    if (
        execute_live is not True or interactive is not True
        or type(confirmation) is not str
        or confirmation != d1_live_preview.CONFIRMATION_PHRASE
    ):
        return d1_live_preview._preview("LIVE_NOT_AUTHORIZED")
    if (
        type(api_key) is not str or not api_key or not api_key.isascii()
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in api_key)
        or (http_transport is not None
            and not isinstance(http_transport, httpx2.BaseTransport))
        or not valid_demo_plan(
            plan, synthetic=isinstance(http_transport, httpx2.MockTransport),
        )
    ):
        return d1_live_preview._preview("BLOCKED_CONFIG", "INVALID_CONFIGURATION")
    result = d1_live_preview._run_validated_preview(
        model=plan.config.model, input_text=plan.input_text,
        timeout=plan.config.timeout, max_output_tokens=plan.config.max_output_tokens,
        config=plan.config, profile=plan.config.profile, api_key=api_key,
        http_transport=http_transport, include_candidate_provenance=True,
    )
    return {**result, "search_profile": plan.config.profile}
