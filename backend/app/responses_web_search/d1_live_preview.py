"""내부 단일 실행 경계. 검색 증거는 독립 원출처 검증·게시 승인이 아니다.

TTY/확인 문구는 실수 방지 절차이며 사용자 인증 수단이 아니다.
MockTransport에서만 합성 실행일을 허용한다. 실제 전송은 현재 서울 날짜의
D0 계획과 일치해야 하며, 이 모듈 import만으로는 I/O를 수행하지 않는다.
"""

import logging
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from threading import get_ident
from typing import get_args

import httpx2

from . import c1_adapter, c2_transport, normalizer, parser, validator
from .gate_d_preflight import GateDPreflightPlan, build_preflight_plan
from .types import SearchRunConfig

CONFIRMATION_PHRASE = "EXECUTE ONE LIVE SEARCH"


def _safety() -> dict[str, object]:
    return {
        "review_status": "REVIEW_REQUIRED",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE",
        "independent_source_verified": False,
    }


def _preview(status: str, *reasons: str) -> dict[str, object]:
    return {
        **_safety(), "mode": "LIVE", "status": status,
        "search_execution": "UNKNOWN", "response_validation": "NOT_EVALUATED",
        "tool_calls_observed": None, "usage": None,
        "reason_codes": list(reasons), "issues": [], "candidates": [],
    }


def _valid_plan(plan: GateDPreflightPlan, *, synthetic: bool) -> bool:
    if (
        type(plan) is not GateDPreflightPlan
        or type(plan.start_date) is not date or type(plan.end_date) is not date
        or type(plan.input_text) is not str
        or plan.live_request_allowed is not False
    ):
        return False
    # Mock test inputs have their own calendar. Never use this anchor for a
    # real transport: old plans must not masquerade as today's execution plan.
    anchor = (
        datetime.combine(plan.end_date, time(), timezone(timedelta(hours=9)))
        if synthetic else None
    )
    expected = build_preflight_plan(config=plan.config, execution_at=anchor)
    return plan == expected


@contextmanager
def _private_sdk_logs():
    """Suppress this thread's SDK/HTTP diagnostics during the bounded request.

    SDK diagnostic records can contain untrusted upstream metadata. Restore
    filters in finally; do not change global levels or suppress other threads.
    Only already-loaded SDK/HTTP loggers are involved, not application logging.
    """
    owner = get_ident()

    class PrivateRun(logging.Filter):
        def filter(self, record):
            return record.thread != owner

    guard = PrivateRun()
    loggers = [
        logger for name, logger in list(logging.Logger.manager.loggerDict.items())
        if isinstance(logger, logging.Logger)
        and name.split(".")[0] in {"openai", "httpx2", "httpcore2"}
    ]
    for logger in loggers:
        logger.addFilter(guard)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(guard)


def _usage(converted: dict[str, object]) -> dict[str, int] | None:
    raw = converted.get("usage")
    names = ("input_tokens", "output_tokens", "total_tokens")
    if not isinstance(raw, dict) or not all(
        type(raw.get(key)) is int and raw[key] >= 0 for key in names
    ):
        return None
    if raw["total_tokens"] != raw["input_tokens"] + raw["output_tokens"]:
        return None
    return {key: raw[key] for key in names}


def run_live_preview(
    *, plan: GateDPreflightPlan, execute_live: bool = False,
    interactive: bool = False, confirmation: str | None = None,
    api_key: str | None = None, http_transport: httpx2.BaseTransport | None = None,
) -> dict[str, object]:
    """별도 승인된 내부 호출을 한 번 실행하고 검증 결과만 반환한다."""
    if (
        execute_live is not True or interactive is not True
        or type(confirmation) is not str or confirmation != CONFIRMATION_PHRASE
    ):
        return _preview("LIVE_NOT_AUTHORIZED")
    try:
        if (
            type(api_key) is not str or not api_key
            or not api_key.isascii()
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127
                   for char in api_key)
            or (http_transport is not None
                and not isinstance(http_transport, httpx2.BaseTransport))
            or not _valid_plan(
                plan, synthetic=isinstance(http_transport, httpx2.MockTransport),
            )
        ):
            return _preview("BLOCKED_CONFIG", "INVALID_CONFIGURATION")
    except Exception:
        return _preview("BLOCKED_CONFIG", "INVALID_CONFIGURATION")

    config = SearchRunConfig(
        profile=plan.config.profile, lookback_days=plan.config.lookback_days,
        max_candidates=plan.config.max_candidates,
        max_tool_calls=plan.config.max_tool_calls,
    )
    try:
        with _private_sdk_logs():
            with httpx2.Client(transport=http_transport, trust_env=False) as client:
                response = c2_transport.request_response(
                    api_key=api_key, model=plan.config.model,
                    input_text=plan.input_text, timeout=plan.config.timeout,
                    max_output_tokens=plan.config.max_output_tokens,
                    http_client=client,
                )
            converted = c1_adapter.convert_response(response)
            normalized = normalizer.normalize_response(converted, config)
            evidence = normalized.execution_evidence
            completed = evidence.completed_search_actions
            preview = _preview("INVALID_OR_INCOMPLETE_RESPONSE")
            preview.update(
                usage=_usage(converted),
                search_execution=(
                    "UNKNOWN" if completed is None
                    else "CONFIRMED" if completed > 0 else "NOT_CONFIRMED"
                ),
                tool_calls_observed=evidence.web_search_calls_observed,
                reason_codes=list(normalized.reason_codes),
            )
            if normalized.outcome == "REJECTED":
                preview["response_validation"] = "INVALID"
                return preview
            parsed = parser.parse_response(normalized.parser_input, config)
            preview["reason_codes"] = list(parsed.reason_codes)
            if parsed.status is not None:
                preview.update(
                    status=parsed.status,
                    response_validation=(
                        "NOT_EVALUATED" if parsed.status == "SEARCH_NOT_EXECUTED"
                        else "INVALID"
                    ),
                )
                return preview
            candidates, issues = validator.validate_candidates(parsed)
            preview.update(
                response_validation="VALID",
                issues=[{"candidate_index": item.candidate_index, "code": item.code}
                        for item in issues],
                candidates=[{
                    **_safety(), "topic_draft": candidate.topic_draft,
                    "source_url": candidate.source_url,
                    "source_title_reference": candidate.source_title_reference,
                    "source_published_at": None,
                    "proposed_category_ref": config.profile,
                } for candidate in candidates],
                status=(
                    "PREVIEW_READY" if candidates
                    else "NO_VALID_CANDIDATES" if parsed.candidates else "EMPTY_RESULT"
                ),
            )
            return preview
    except c2_transport.C2TransportError as error:
        if error.code not in get_args(c2_transport.C2ErrorCode):
            return _preview("UPSTREAM_ERROR", "UNEXPECTED_ERROR")
        return _preview(
            "BLOCKED_CONFIG" if error.code == "INVALID_CONFIGURATION"
            else "UPSTREAM_ERROR", error.code,
        )
    except c1_adapter.C1ConversionError:
        return _preview("INVALID_OR_INCOMPLETE_RESPONSE", "C1_CONVERSION_FAILED")
    except Exception:
        # Never stringify/log/chain an unexpected exception. A sent request may
        # already have been processed remotely; no second request is attempted.
        return _preview("UPSTREAM_ERROR", "UNEXPECTED_ERROR")
