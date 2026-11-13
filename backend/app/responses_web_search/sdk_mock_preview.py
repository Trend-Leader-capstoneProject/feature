"""Mock HTTP → SDK → C1 → S1/S0의 메모리 전용 비게시 연결.

SDK_MOCK의 검색 증거는 주입된 Mock 데이터에 한정된다. 실제 검색 실행,
비용 발생, 원출처 검증 또는 게시 승인을 의미하지 않는다.
"""

import httpx2

from .c1_adapter import C1ConversionError, convert_response
from .c2_transport import C2TransportError, request_response
from .normalizer import normalize_response
from .parser import parse_response
from .types import SearchRunConfig
from .validator import validate_candidates


def _safety() -> dict[str, object]:
    return {
        "review_status": "REVIEW_REQUIRED",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE",
        "independent_source_verified": False,
    }


def run_sdk_mock_preview(
    *,
    api_key: str,
    model: str,
    input_text: str,
    timeout: float,
    config: SearchRunConfig,
    mock_transport: httpx2.MockTransport,
) -> dict[str, object]:
    """실행별 Client로 한 번 요청하고 기존 검증 결과만 Preview로 투영한다."""
    preview: dict[str, object] = {
        **_safety(),
        "mode": "SDK_MOCK",
        "status": "UPSTREAM_ERROR",
        "search_execution": "UNKNOWN",
        "response_validation": "NOT_EVALUATED",
        "tool_calls_observed": None,
        "request_started_at_utc": None,
        "response_received_at_utc": None,
        "reason_codes": [],
        "issues": [],
        "candidates": [],
    }
    if not isinstance(mock_transport, httpx2.MockTransport):
        preview.update(
            status="BLOCKED_CONFIG", reason_codes=["INVALID_CONFIGURATION"],
        )
        return preview

    try:
        # C2의 SDK 컨텍스트도 Client를 닫는다. 바깥 컨텍스트는 C2 사전
        # 검증에서 SDK를 열기 전에 실패하는 경우까지 종료를 보장한다.
        with httpx2.Client(transport=mock_transport, trust_env=False) as client:
            response = request_response(
                api_key=api_key, model=model, input_text=input_text,
                timeout=timeout, http_client=client,
            )
    except C2TransportError as error:
        preview.update(
            status=(
                "BLOCKED_CONFIG" if error.code == "INVALID_CONFIGURATION"
                else "UPSTREAM_ERROR"
            ),
            reason_codes=[error.code],
        )
        return preview

    try:
        converted = convert_response(response)
    except C1ConversionError:
        preview.update(
            status="INVALID_OR_INCOMPLETE_RESPONSE",
            reason_codes=["C1_CONVERSION_FAILED"],
        )
        return preview

    normalized = normalize_response(converted, config)
    evidence = normalized.execution_evidence
    completed_searches = evidence.completed_search_actions
    preview.update(
        search_execution=(
            "UNKNOWN" if completed_searches is None
            else "CONFIRMED" if completed_searches > 0
            else "NOT_CONFIRMED"
        ),
        tool_calls_observed=evidence.web_search_calls_observed,
        reason_codes=list(normalized.reason_codes),
    )
    if normalized.outcome == "REJECTED":
        preview.update(
            status="INVALID_OR_INCOMPLETE_RESPONSE",
            response_validation="INVALID",
        )
        return preview

    parsed = parse_response(normalized.parser_input, config)
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

    candidates, issues = validate_candidates(parsed)
    preview["response_validation"] = "VALID"
    preview["issues"] = [
        {"candidate_index": issue.candidate_index, "code": issue.code}
        for issue in issues
    ]
    preview["candidates"] = [
        {
            **_safety(),
            "topic_draft": candidate.topic_draft,
            "source_url": candidate.source_url,
            "source_title_reference": candidate.source_title_reference,
            "source_published_at": None,
            "proposed_category_ref": config.profile,
        }
        for candidate in candidates
    ]
    preview["status"] = (
        "PREVIEW_READY" if candidates
        else "NO_VALID_CANDIDATES" if parsed.candidates
        else "EMPTY_RESULT"
    )
    return preview
