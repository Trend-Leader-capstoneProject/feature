"""S0 유스케이스 조정과 비게시 Preview 투영. 외부 I/O 없음."""

from .fixture_adapter import FixtureAdapter, FixtureUpstreamError
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


def run_preview(
    *, config: SearchRunConfig, adapter: FixtureAdapter,
) -> dict[str, object]:
    preview = {
        **_safety(),
        "mode": "FIXTURE_ONLY",
        "status": "UPSTREAM_ERROR",
        "searched_at_utc": None,
        "fixture_reference_at_utc": (
            config.fixture_reference_at_utc.isoformat()
            if config.fixture_reference_at_utc is not None else None
        ),
        "lookback_days": config.lookback_days,
        "simulated_web_search_executed": False,
        "tool_calls_observed": 0,
        "reason_codes": [],
        "issues": [],
        "candidates": [],
    }
    try:
        response = adapter.read()
    except FixtureUpstreamError as error:
        preview["reason_codes"] = [error.kind]
        return preview
    parsed = parse_response(response, config)
    preview.update(
        simulated_web_search_executed=parsed.simulated_web_search_executed,
        tool_calls_observed=parsed.tool_calls_observed,
        reason_codes=list(parsed.reason_codes),
    )
    if parsed.status is not None:
        preview["status"] = parsed.status
        return preview
    candidates, issues = validate_candidates(parsed)
    preview["issues"] = [
        {"candidate_index": issue.candidate_index, "code": issue.code}
        for issue in issues
    ]
    preview["candidates"] = [
        {
            **_safety(),
            "topic_draft": item.topic_draft,
            "source_url": item.source_url,
            "source_title_reference": item.source_title_reference,
            "source_published_at": None,
            "proposed_category_ref": config.profile,
        }
        for item in candidates
    ]
    preview["status"] = (
        "PREVIEW_READY" if candidates
        else "NO_VALID_CANDIDATES" if parsed.candidates
        else "EMPTY_RESULT"
    )
    return preview
