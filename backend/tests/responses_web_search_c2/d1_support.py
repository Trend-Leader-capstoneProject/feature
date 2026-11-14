"""D1-only test controls; no executor, authorization implementation or Preview."""

import builtins
import importlib
import importlib.abc
import io
import json
import os
import sys
from datetime import datetime, timezone

import httpx2
import openai
import pytest
from support import API_KEY, MARKER, OPTIONS
from test_sdk_mock_preview_red import assert_flow, payload_for

from app.responses_web_search.gate_d_preflight import build_preflight_plan

PHRASE = "EXECUTE ONE LIVE SEARCH"
INSTANT = datetime(2031, 1, 2, 3, 0, tzinfo=timezone.utc)
LIVE = "app.responses_web_search.d1_live_preview"
CLI = "app.responses_web_search.d1_cli"
USAGE = {"input_tokens": 120, "output_tokens": 35, "total_tokens": 155}


class Terminal(io.StringIO):
    def __init__(self, text="", *, tty=True, interrupt=None):
        super().__init__(text)
        self.tty = tty
        self.interrupt = interrupt
        self.reads = 0

    def isatty(self):
        return self.tty

    def readline(self, *args, **kwargs):
        self.reads += 1
        if self.interrupt:
            raise self.interrupt()
        return super().readline(*args, **kwargs)


def product(name):
    # Absence must fail in the test body, never skip/xfail or fail collection.
    return (importlib.reload(sys.modules[name]) if name in sys.modules
            else importlib.import_module(name))


def plan():
    return build_preflight_plan(execution_at=INSTANT)


def invoke(module, endpoint, **overrides):
    args = dict(
        plan=plan(), execute_live=True, interactive=True, confirmation=PHRASE,
        api_key=API_KEY, http_transport=httpx2.MockTransport(endpoint.handle),
    )
    args.update(overrides)
    return module.run_live_preview(**args)


def cli(module, endpoint, *, argv=(), stdin=None, stdout=None):
    stdin = Terminal(PHRASE + "\n") if stdin is None else stdin
    stdout = Terminal() if stdout is None else stdout
    stderr = Terminal()
    code = module.main(
        list(argv), stdin=stdin, stdout=stdout, stderr=stderr,
        execution_at=INSTANT, http_transport=httpx2.MockTransport(endpoint.handle),
    )
    return code, stdin, stdout.getvalue(), stderr.getvalue()


def assert_request(endpoint, approved_plan):
    assert len(endpoint.calls) == 1
    request, = endpoint.calls
    expected = OPTIONS | {
        "model": approved_plan.config.model, "input": approved_plan.input_text,
        "max_output_tokens": approved_plan.config.max_output_tokens,
    }
    body = json.loads(request.content)
    for key, value in expected.items():
        assert body[key] == value
    assert body.get("background", False) is False
    assert request.extensions["timeout"] == dict.fromkeys(
        ("connect", "read", "write", "pool"), approved_plan.config.timeout,
    )


def assert_safe(preview, caplog, capsys, *extra):
    assert json.loads(json.dumps(preview, allow_nan=False)) == preview
    assert preview["mode"] == "LIVE"
    for item in (preview, *preview["candidates"]):
        assert item["review_status"] == "REVIEW_REQUIRED"
        assert item["publication_status"] == "NOT_FOR_PUBLICATION"
        assert item["publish_authorization"] == "NONE"
        assert item["independent_source_verified"] is False
        for key in ("observed_at_utc", "cost", "actual_cost", "rank", "ranking"):
            assert item.get(key) is None
    for candidate in preview["candidates"]:
        assert candidate["source_published_at"] is None
        assert candidate["proposed_category_ref"] == "IT_DIGITAL"
    captured = capsys.readouterr()
    visible = "\n".join((
        repr(preview), caplog.text, captured.out, captured.err, *extra,
    ))
    for secret in (API_KEY, MARKER, "Bearer ", "authorization", "RAW_D1_CONTENT"):
        assert secret not in visible


@pytest.fixture
def no_dispatch(monkeypatch):
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("dispatch")
        raise AssertionError("D1 unauthorized dispatch")

    for cls in (openai.OpenAI, openai.AsyncOpenAI):
        monkeypatch.setattr(cls, "__init__", blocked)
    for cls in (openai.resources.responses.Responses,
                openai.resources.responses.AsyncResponses):
        monkeypatch.setattr(cls, "create", blocked)
    for cls in (httpx2.Client, httpx2.AsyncClient):
        monkeypatch.setattr(cls, "send", blocked)
    transport = importlib.import_module("app.responses_web_search.c2_transport")
    monkeypatch.setattr(transport, "request_response", blocked)
    yield attempts
    assert attempts == [], "Unauthorized dispatch, including swallowed failures"


@pytest.fixture
def d1_isolation(monkeypatch):
    """Extend C2 guards: count swallowed forbidden imports and real HTTP sends."""
    attempts, expected = [], []

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            operational = fullname.split(".")[0] in {
                "sqlalchemy", "pymysql", "sqlite3", "redis", "dotenv",
            }
            if operational or (fullname.startswith("app.") and not (
                fullname == "app.responses_web_search"
                or fullname.startswith("app.responses_web_search.")
            )):
                attempts.append("operational-import")
                raise AssertionError("D1 operational import forbidden")
            return None

    def blocked(*args, **kwargs):
        attempts.append("real-http")
        raise AssertionError("D1 real HTTP transport forbidden")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", blocked)

    def guard_open(original):
        def guarded(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                attempts.append("file-write")
                raise AssertionError("D1 file write forbidden")
            return original(file, mode, *args, **kwargs)
        return guarded

    monkeypatch.setattr(builtins, "open", guard_open(builtins.open))
    monkeypatch.setattr(io, "open", guard_open(io.open))
    original_os_open = os.open

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            attempts.append("file-write")
            raise AssertionError("D1 file write forbidden")
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", guarded_os_open)
    guard = Guard()
    sys.meta_path.insert(0, guard)
    # Keep the SDK Mock product entrypoint unavailable to the new Live path.
    mock_module = importlib.import_module("app.responses_web_search.sdk_mock_preview")

    def no_mock_executor(*args, **kwargs):
        attempts.append("mock-executor")
        raise AssertionError("D1 cannot reuse SDK Mock executor")

    monkeypatch.setattr(mock_module, "run_sdk_mock_preview", no_mock_executor)
    try:
        yield expected
    finally:
        sys.meta_path.remove(guard)
        assert attempts == expected, "Unexpected or swallowed D1 external effect"


def expected_flow(case):
    return {
        "ready": ["c2", "c1", "normalize", "parse", "validate"],
        "rejected": ["c2", "c1", "normalize"],
        "no-search": ["c2", "c1", "normalize", "parse"],
        "empty": ["c2", "c1", "normalize", "parse", "validate"],
    }[case]


__all__ = [
    "assert_flow", "payload_for", "d1_isolation", "no_dispatch",
]
