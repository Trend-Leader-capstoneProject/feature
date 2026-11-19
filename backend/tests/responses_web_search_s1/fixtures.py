"""Synthetic F-BASE from frozen AC v0.2.2, never a recorded API response."""

import json

URL = "https://vendor.example.test/releases/1"
TEXT = (
    '{"candidates":[{"topic_draft":"가상 기기 출시",'
    '"source_url":"https://vendor.example.test/releases/1",'
    '"source_title_reference":"가상 공식 발표"}]}'
)


def response():
    return {
        "id": "resp_synthetic_s1",
        "status": "completed",
        "output": [
            {
                "id": "ws_synthetic_s1",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "합성 IT 최근 7일"},
            },
            {
                "id": "msg_synthetic_s1",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": TEXT,
                    "annotations": [{
                        "type": "url_citation",
                        "url": URL,
                        "title": "합성 인용",
                        "start_index": 55,
                        "end_index": 93,
                    }],
                }],
            },
        ],
    }


def content(payload):
    return payload["output"][1]["content"][0]


def reasoning(index=0):
    return {
        "id": f"rs_synthetic_{index}", "type": "reasoning",
        "summary": [], "status": "completed",
    }


def padded_response(byte_count):
    payload = response()
    # Keep the original JSON/URL prefix and citation offsets intact. The extra
    # root field is ignored by S0; multibyte padding detects character counting.
    prefix = TEXT[:-1] + ',"padding":"'
    remaining = byte_count - len((prefix + '"}').encode("utf-8"))
    padding = "한" * (remaining // 3) + "x" * (remaining % 3)
    text = prefix + padding + '"}'
    assert len(text.encode("utf-8")) == byte_count
    assert len(text) < 32768
    assert json.loads(text)["candidates"] == json.loads(TEXT)["candidates"]
    content(payload)["text"] = text
    return payload
