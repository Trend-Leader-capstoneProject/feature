"""Gate B 합성 Preview 조정. SDK·외부 I/O·게시·영속화는 수행하지 않는다."""

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


def run_synthetic_preview(
    *, config: SearchRunConfig, adapter,
) -> dict[str, object]:
    """주입된 Mock을 한 번 읽고 기존 검증 계층의 결과만 투영한다."""
    preview = {
        **_safety(),
        "mode": "S1_SYNTHETIC",
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
    try:
        response = adapter.read()
    except TimeoutError:
        # 예외 원문이나 임의의 신규 진단 코드를 Preview에 복사하지 않는다.
        return preview

    normalized = normalize_response(response, config)
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
