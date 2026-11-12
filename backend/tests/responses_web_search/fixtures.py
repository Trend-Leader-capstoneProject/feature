"""Synthetic dictionaries; never downloaded responses or SDK objects."""

import json


def candidate(topic="가상 기기 출시", url="https://vendor.example.test/releases/1"):
    return {
        "topic_draft": topic,
        "source_url": url,
        "source_title_reference": "가상 공식 발표",
    }


def response(candidates=None):
    candidates = [candidate()] if candidates is None else candidates
    text = json.dumps({"candidates": candidates}, ensure_ascii=False)
    annotations = []
    for item in candidates:
        url = item.get("source_url")
        if isinstance(url, str) and url:
            encoded_url = json.dumps(url, ensure_ascii=False)[1:-1]
            start = text.index(encoded_url)
            annotations.append({
                "type": "url_citation",
                "url": url,
                "title": "합성 인용",
                "start_index": start,
                "end_index": start + len(encoded_url),
            })
    return {
        "id": "resp_synthetic_s0",
        "status": "completed",
        "output": [
            {
                "id": "ws_synthetic_s0",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "합성 IT 최근 7일"},
            },
            {
                "id": "msg_synthetic_s0",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{
                    "type": "output_text", "text": text,
                    "annotations": annotations,
                }],
            },
        ],
    }
