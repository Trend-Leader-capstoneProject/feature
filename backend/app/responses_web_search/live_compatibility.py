"""Approved Gate C D2 envelope, retaining every original tool item and status."""

from . import normalizer, parser
from .types import ParsedResponse
from .validation_limits import ValidationLimits


def parse_d2_response(
    response: dict[str, object], config: ValidationLimits, *,
    request_max_tool_calls: object, allow_pending_open_page: bool = False,
) -> ParsedResponse | None:
    """Preserve D2; opt in only for a pending demo open_page attempt."""
    if (
        type(request_max_tool_calls) is not int or request_max_tool_calls != 1
        or type(allow_pending_open_page) is not bool
        or response.get("status") != "completed"
        or response.get("error") is not None
        or response.get("incomplete_details") is not None
    ):
        return None
    output = response.get("output")
    if (
        not isinstance(output, list) or len(output) > normalizer._MAX_OUTPUT_ITEMS
        or not all(isinstance(item, dict) for item in output)
    ):
        return None
    calls = [item for item in output if item.get("type") == "web_search_call"]
    if len(calls) != 2:
        return None
    states = []
    actions_and_states = []
    messages = []
    for item in output:
        kind = item.get("type")
        if kind == "web_search_call":
            action = item.get("action")
            action_type = action.get("type") if isinstance(action, dict) else None
            status = item.get("status")
            if action_type != "search" and not (
                allow_pending_open_page
                and action_type == "open_page" and status == "searching"
            ):
                return None
            states.append(status)
            actions_and_states.append((action_type, status))
        elif kind == "reasoning":
            if (
                not isinstance(item.get("id"), str) or not item["id"]
                or not isinstance(item.get("summary"), list)
                or ("status" in item and item["status"] != "completed")
            ):
                return None
        elif kind == "message":
            if (
                item.get("status") != "completed" or item.get("role") != "assistant"
                or item.get("phase", "final_answer") != "final_answer"
            ):
                return None
            messages.append(item)
        else:
            return None
    if states.count("completed") != 1 or states.count("searching") != 1:
        return None
    if any(action == "open_page" for action, _ in actions_and_states) and (
        actions_and_states != [("search", "completed"), ("open_page", "searching")]
    ):
        return None
    if len(messages) != 1:
        return None
    content = messages[0].get("content")
    if (
        not isinstance(content, list) or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "output_text"
        or not isinstance(content[0].get("text"), str)
    ):
        return None
    part = content[0]
    try:
        if len(part["text"].encode("utf-8")) > normalizer._MAX_TEXT_BYTES:
            return None
    except UnicodeEncodeError:
        return None
    annotations = part.get("annotations")
    if isinstance(annotations, list) and len(annotations) > normalizer._MAX_ANNOTATIONS:
        return None
    return parser.parse_candidate_content(part, config, calls=2, searched=True)
