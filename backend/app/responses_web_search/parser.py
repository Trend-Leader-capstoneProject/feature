"""제한된 합성 응답 프로필을 파싱한다. 실제 SDK 호환성을 보장하지 않는다."""

import json

from .types import ParsedResponse, SearchRunConfig


def parse_response(response: object, config: SearchRunConfig) -> ParsedResponse:
    calls = 0
    searched = False

    def invalid(reason: str = "RESPONSE_STRUCTURE_INVALID") -> ParsedResponse:
        return ParsedResponse(
            status="INVALID_OR_INCOMPLETE_RESPONSE",
            tool_calls_observed=calls,
            simulated_web_search_executed=searched,
            reason_codes=(reason,),
        )

    if not isinstance(response, dict) or response.get("status") != "completed":
        return invalid()
    output = response.get("output")
    if not isinstance(output, list) or not all(
        isinstance(item, dict) for item in output
    ):
        return invalid()
    calls = sum(item.get("type") == "web_search_call" for item in output)
    if calls > config.max_tool_calls:
        return invalid("TOOL_CALL_LIMIT_EXCEEDED")

    messages = []
    for item in output:
        if item.get("status") != "completed":
            return invalid()
        if item.get("type") == "web_search_call":
            action = item.get("action")
            if not isinstance(action, dict) or not isinstance(action.get("type"), str):
                return invalid()
            searched = action["type"] == "search"
        elif item.get("type") == "message":
            messages.append(item)
        else:
            return invalid()

    if len(messages) != 1 or messages[0].get("role") != "assistant":
        return invalid()
    content = messages[0].get("content")
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "output_text"
        or not isinstance(content[0].get("text"), str)
    ):
        return invalid()
    if not searched:
        return ParsedResponse(
            status="SEARCH_NOT_EXECUTED", tool_calls_observed=calls,
        )

    annotations = content[0].get("annotations")
    if not isinstance(annotations, list):
        return invalid()
    citation_urls = set()
    for annotation in annotations:
        if (
            not isinstance(annotation, dict)
            or annotation.get("type") != "url_citation"
            or not isinstance(annotation.get("url"), str)
            or not annotation["url"].strip()
        ):
            return invalid("ANNOTATION_STRUCTURE_INVALID")
        citation_urls.add(annotation["url"])

    try:
        payload = json.loads(content[0]["text"])
    except (ValueError, RecursionError):
        return invalid()
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        return invalid()
    candidates = payload["candidates"]
    if len(candidates) > config.max_candidates:
        return invalid("CANDIDATE_LIMIT_EXCEEDED")
    if not all(isinstance(item, dict) for item in candidates):
        return invalid()
    return ParsedResponse(
        status=None,
        tool_calls_observed=calls,
        simulated_web_search_executed=True,
        candidates=tuple(candidates),
        citation_urls=frozenset(citation_urls),
    )
