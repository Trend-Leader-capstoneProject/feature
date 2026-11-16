"""D0-04~08: proposed offline-only interface, never a Live Preview.

Proposed product module: app.responses_web_search.gate_d_preflight
  GateDConfig: frozen dataclass with the exact first-run settings below.
  build_preflight_plan(*, config=GateDConfig(), execution_at=None)
    -> frozen GateDPreflightPlan dataclass (fields asserted below).
  GateDPreflightError.code == INVALID_CONFIGURATION for invalid policy/time.

execution_at is an aware instant; None means current time. Date range includes
the execution day in Asia/Seoul. No key/client/authorization input or executor.
These names are internal interface proposals, not new public/Frozen API fields.
"""

import dataclasses
import importlib
import os
from datetime import date, datetime, timedelta, timezone

import httpx2
import openai
import pytest

POLICY = {
    "model": "gpt-6-luna", "profile": "IT_DIGITAL", "lookback_days": 7,
    "max_candidates": 3, "timeout": 60.0, "max_output_tokens": 4096,
    "max_tool_calls": 1, "max_retries": 0, "store": False, "stream": False,
}
PLAN_FIELDS = {
    "config", "status", "live_request_allowed", "timezone",
    "start_date", "end_date", "input_text",
}


@pytest.fixture(autouse=True)
def no_request_dispatch(monkeypatch):
    """In addition to C2 I/O guards, reject even in-memory SDK dispatch."""
    attempts = []
    expected = []

    def blocked(*args, **kwargs):
        attempts.append("dispatch")
        raise AssertionError("D0 must not construct a client or dispatch requests")

    monkeypatch.setattr(openai.OpenAI, "__init__", blocked)
    monkeypatch.setattr(openai.AsyncOpenAI, "__init__", blocked)
    monkeypatch.setattr(openai.resources.responses.Responses, "create", blocked)
    monkeypatch.setattr(openai.resources.responses.AsyncResponses, "create", blocked)
    monkeypatch.setattr(httpx2.Client, "send", blocked)
    monkeypatch.setattr(httpx2.AsyncClient, "send", blocked)
    transport = importlib.import_module("app.responses_web_search.c2_transport")
    monkeypatch.setattr(transport, "request_response", blocked)
    yield expected
    assert attempts == expected, "D0 attempted dispatch, including swallowed failures"


def test_d0_dispatch_guard_control(no_request_dispatch):
    """Only this sensitivity control deliberately exercises blocked entrypoints."""
    transport = importlib.import_module("app.responses_web_search.c2_transport")
    probes = (
        openai.OpenAI, openai.AsyncOpenAI,
        openai.resources.responses.Responses.create,
        openai.resources.responses.AsyncResponses.create,
        httpx2.Client.send, httpx2.AsyncClient.send, transport.request_response,
    )
    for probe in probes:
        with pytest.raises(AssertionError, match="D0 must not construct"):
            probe()
    no_request_dispatch.extend(["dispatch"] * len(probes))


def preflight_module():
    # Missing product module is a test failure, never a collection/fixture error.
    return importlib.import_module("app.responses_web_search.gate_d_preflight")


def assert_plan(plan, start, end):
    assert dataclasses.is_dataclass(plan)
    assert {field.name for field in dataclasses.fields(plan)} == PLAN_FIELDS
    assert dataclasses.asdict(plan.config) == POLICY
    assert plan.status == "PREFLIGHT_VALIDATED"
    assert plan.live_request_allowed is False
    assert plan.timezone == "Asia/Seoul"
    assert plan.start_date == start
    assert plan.end_date == end
    assert (end - start).days == 6
    assert isinstance(plan.input_text, str) and plan.input_text.strip()
    assert start.isoformat() in plan.input_text
    assert end.isoformat() in plan.input_text
    assert "대한민국" in plan.input_text
    assert "IT" in plan.input_text and "디지털" in plan.input_text
    assert "3" in plan.input_text
    assert "최대 3건" in plan.input_text
    assert '{"candidates":[' in plan.input_text
    for field in ("topic_draft", "source_url", "source_title_reference"):
        assert field in plan.input_text
    assert "JSON 본문만" in plan.input_text
    assert "설명문" in plan.input_text and "Markdown 코드 블록" in plan.input_text
    assert "포함하지" in plan.input_text
    assert "source_url과 인용 URL" in plan.input_text and "동일" in plan.input_text
    assert "인기도·랭킹·출처 게시일" in plan.input_text
    assert "생성하지" in plan.input_text
    # Requested candidate fields must not demand invented metrics or dates.
    for field in ("popularity_score", "rank", "source_published_at"):
        assert field not in plan.input_text
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.live_request_allowed = True
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.config.model = "unapproved-model"


@pytest.mark.parametrize("instant,start,end", [
    (datetime(2031, 1, 1, 14, 59, tzinfo=timezone.utc),
     date(2030, 12, 26), date(2031, 1, 1)),
    (datetime(2031, 1, 1, 15, 0, tzinfo=timezone.utc),
     date(2030, 12, 27), date(2031, 1, 2)),
], ids=["before-seoul-midnight", "at-seoul-midnight"])
def test_d0_04_05_08_policy_calendar_and_offline_meaning(instant, start, end):
    module = preflight_module()
    plan = module.build_preflight_plan(execution_at=instant)
    assert_plan(plan, start, end)


def test_d0_04_default_execution_date_is_current_seoul_day():
    module = preflight_module()
    seoul = timezone(timedelta(hours=9))
    before = datetime.now(seoul).date()
    plan = module.build_preflight_plan()
    after = datetime.now(seoul).date()
    assert plan.end_date in (before, after)
    assert_plan(plan, plan.end_date - timedelta(days=6), plan.end_date)


@pytest.mark.parametrize("overrides", [
    {"model": "unapproved-model"}, {"profile": "OTHER"},
    {"lookback_days": 8}, {"max_candidates": 4}, {"timeout": 30.0},
    {"max_output_tokens": 8192}, {"max_tool_calls": 2}, {"max_retries": 1},
    {"store": True}, {"stream": True},
], ids=["model-no-fallback", "profile", "lookback", "candidates", "timeout",
        "output-limit", "tool-limit", "retries", "store", "stream"])
def test_d0_04_unapproved_policy_is_rejected(overrides):
    module = preflight_module()
    with pytest.raises(module.GateDPreflightError) as caught:
        config = module.GateDConfig(**(POLICY | overrides))
        module.build_preflight_plan(config=config)
    assert caught.value.code == "INVALID_CONFIGURATION"


def test_d0_04_naive_execution_instant_is_rejected():
    module = preflight_module()
    with pytest.raises(module.GateDPreflightError) as caught:
        module.build_preflight_plan(execution_at=datetime(2031, 1, 1))
    assert caught.value.code == "INVALID_CONFIGURATION"


@pytest.mark.parametrize("key_present", [False, True], ids=["no-key", "synthetic-key"])
def test_d0_05_06_key_presence_cannot_authorize_or_leak(
    monkeypatch, key_present, caplog, capsys,
):
    # Existing isolated_io replaced the environment without reading real values.
    marker = "D0_SYNTHETIC_INVALID_KEY_NEVER_USE"
    if key_present:
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", marker)
    module = preflight_module()
    module = importlib.reload(module)  # Import-time effects are guarded too.
    config = module.GateDConfig()
    plan = module.build_preflight_plan(config=config)
    assert plan.live_request_allowed is False
    assert plan.status == "PREFLIGHT_VALIDATED"
    captured = capsys.readouterr()
    visible = repr(plan) + repr(config) + caplog.text + captured.out + captured.err
    assert marker not in visible
    assert "Bearer " not in visible
    assert {field.name for field in dataclasses.fields(plan)} == PLAN_FIELDS
