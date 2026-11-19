"""Gate A/B 합성 프로필의 순수 검증·투영. 실제 SDK 호환성은 미검증이다.

후보 JSON과 인용 URL 구조는 S0의 책임이다. 여기서는 Parser/Validator를
호출하지 않으며, NORMALIZED가 후보 유효성이나 게시 승인을 뜻하지 않는다.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

from .types import SearchRunConfig

_MAX_OUTPUT_ITEMS = 16
_MAX_TEXT_BYTES = 32768
_MAX_ANNOTATIONS = 32


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    response_status: str = "UNKNOWN"
    web_search_calls_observed: int | None = None
    completed_search_actions: int | None = None
    assistant_messages_observed: int | None = None


@dataclass(frozen=True, slots=True)
class CitationTrace:
    """원본 위치만 추적한다. offset·URL의 의미나 사실성을 검증하지 않는다."""

    output_index: int
    content_index: int
    annotation_index: int
    url: object = field(repr=False)
    start_index: object = field(repr=False)
    end_index: object = field(repr=False)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    outcome: Literal["NORMALIZED", "REJECTED"]
    execution_evidence: ExecutionEvidence
    parser_input: dict[str, object] | None = field(default=None, repr=False)
    citation_trace: tuple[CitationTrace, ...] = field(default=(), repr=False)
    reason_codes: tuple[str, ...] = ()


def normalize_response(
    response: object, config: SearchRunConfig,
) -> NormalizationResult:
    """전체 원본 검증 후 정상 reasoning만 제외한 독립 사본을 반환한다."""
    status = response.get("status") if isinstance(response, dict) else None
    output = response.get("output") if isinstance(response, dict) else None
    evidence = ExecutionEvidence(
        response_status=status if isinstance(status, str) else "UNKNOWN",
    )
    # 파손된 목록의 부분 집계를 관찰된 0건으로 승격하지 않는다.
    valid_output = isinstance(output, list) and all(
        isinstance(item, dict) for item in output
    )
    if valid_output:
        evidence = ExecutionEvidence(
            response_status=evidence.response_status,
            web_search_calls_observed=sum(
                item.get("type") == "web_search_call" for item in output
            ),
            completed_search_actions=sum(
                item.get("type") == "web_search_call"
                and item.get("status") == "completed"
                and isinstance(item.get("action"), dict)
                and item["action"].get("type") == "search"
                for item in output
            ),
            assistant_messages_observed=sum(
                item.get("type") == "message" and item.get("role") == "assistant"
                for item in output
            ),
        )

    def reject(reason: str = "RESPONSE_STRUCTURE_INVALID") -> NormalizationResult:
        # 고정 식별자만 사용하고 응답 본문·예외 문자열은 진단에 복사하지 않는다.
        return NormalizationResult(
            outcome="REJECTED", execution_evidence=evidence, reason_codes=(reason,),
        )

    if status != "completed" or not valid_output:
        return reject()
    if evidence.web_search_calls_observed > config.max_tool_calls:
        return reject("TOOL_CALL_LIMIT_EXCEEDED")

    # 상한 검사·투영 전에 원본의 명시적 실패·미완료를 확인한다.
    for item in output:
        if item.get("type") in ("web_search_call", "message"):
            if item.get("status") != "completed":
                return reject()
        elif item.get("type") == "reasoning":
            if "status" in item and item["status"] != "completed":
                return reject()

    if len(output) > _MAX_OUTPUT_ITEMS:
        return reject("S1_OUTPUT_ITEMS_LIMIT_EXCEEDED")
    # 전체 후보 텍스트를 검사해 TEXT_BYTES → ANNOTATIONS 우선순위를 유지한다.
    texts = [
        part
        for item in output
        if item.get("type") == "message" and isinstance(item.get("content"), list)
        for part in item["content"]
        if isinstance(part, dict) and part.get("type") == "output_text"
    ]
    for part in texts:
        text = part.get("text")
        if isinstance(text, str):
            try:
                byte_count = len(text.encode("utf-8"))
            except UnicodeEncodeError:
                return reject()
            if byte_count > _MAX_TEXT_BYTES:
                return reject("S1_TEXT_BYTES_LIMIT_EXCEEDED")
    for part in texts:
        annotations = part.get("annotations")
        if isinstance(annotations, list) and len(annotations) > _MAX_ANNOTATIONS:
            return reject("S1_ANNOTATIONS_LIMIT_EXCEEDED")

    messages = []
    for index, item in enumerate(output):
        kind = item.get("type")
        if kind == "web_search_call":
            action = item.get("action")
            if not isinstance(action, dict) or action.get("type") not in (
                "search", "open_page", "find_in_page",
            ):
                return reject()
        elif kind == "reasoning":
            if (
                not isinstance(item.get("id"), str)
                or not item["id"]
                or not isinstance(item.get("summary"), list)
            ):
                return reject()
        elif kind == "message":
            if item.get("role") != "assistant":
                return reject()
            messages.append((index, item))
        else:
            return reject()

    if len(messages) != 1:
        return reject()
    message_index, message = messages[0]
    content = message.get("content")
    # 단일 output_text 이외에는 Refusal 혼재를 포함해 선택·병합하지 않는다.
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "output_text"
        or not isinstance(content[0].get("text"), str)
    ):
        return reject()

    traces = []
    annotations = content[0].get("annotations")
    if isinstance(annotations, list):
        for index, annotation in enumerate(annotations):
            # URL 누락·비문자열과 annotations 구조 오류는 S0에 위임한다.
            # 명시된 미지원 타입은 S1 호환성 경계에서 거부한다.
            if isinstance(annotation, dict):
                kind = annotation.get("type")
                if isinstance(kind, str) and kind != "url_citation":
                    return reject()
                if kind == "url_citation":
                    traces.append(CitationTrace(
                        output_index=message_index,
                        content_index=0,
                        annotation_index=index,
                        url=deepcopy(annotation.get("url")),
                        start_index=deepcopy(annotation.get("start_index")),
                        end_index=deepcopy(annotation.get("end_index")),
                    ))

    return NormalizationResult(
        outcome="NORMALIZED",
        execution_evidence=evidence,
        parser_input={
            "status": status,
            "output": [
                deepcopy(item) for item in output if item["type"] != "reasoning"
            ],
        },
        citation_trace=tuple(traces),
    )
