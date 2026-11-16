"""Six-category entrypoint under the existing C2 network/DB isolation guards."""

import importlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timezone

import httpx2
import pytest
from d1_support import (
    INSTANT,
    PHRASE,
    Terminal,
    assert_request,
    d1_isolation as d1_isolation,
    no_dispatch as no_dispatch,
)
from support import API_KEY, MARKER
from test_mvp_preview import payload_for

PROFILES = (
    "FASHION", "BEAUTY", "GAME", "FOOD", "ENTERTAINMENT", "IT_DIGITAL",
)
pytestmark = pytest.mark.usefixtures("d1_isolation")


@pytest.fixture(autouse=True)
def scoped_live_clock(monkeypatch):
    # Older D1 tests assign a synthetic clock directly to the cached module.
    # Scope our clock explicitly so these tests are independent of that order.
    from app.responses_web_search import d1_live_preview

    monkeypatch.setattr(d1_live_preview, "datetime", datetime)


def product():
    return importlib.import_module("app.responses_web_search.demo_search")


def plan(profile="FASHION"):
    module = product()
    return module.build_demo_plan(
        config=module.DemoSearchConfig(profile=profile), execution_at=INSTANT,
    )


def invoke(endpoint, **overrides):
    arguments = dict(
        plan=plan(), execute_live=True, interactive=True, confirmation=PHRASE,
        api_key=API_KEY, http_transport=httpx2.MockTransport(endpoint.handle),
    )
    arguments.update(overrides)
    return product().run_demo_preview(**arguments)


def cli(endpoint, args, *, stdin=None, stdout=None, **overrides):
    module = importlib.import_module("app.responses_web_search.demo_cli")
    output = Terminal() if stdout is None else stdout
    error = Terminal()
    arguments = dict(
        stdin=Terminal(PHRASE + "\n") if stdin is None else stdin,
        stdout=output, stderr=error, execution_at=INSTANT,
        http_transport=httpx2.MockTransport(endpoint.handle),
    )
    arguments.update(overrides)
    code = module.main(args, **arguments)
    return code, output.getvalue(), error.getvalue()


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("profile", PROFILES)
def test_six_plans_are_offline_and_explicit(profile):
    approved = plan(profile)
    assert approved.config.profile == profile
    assert approved.start_date == date(2030, 12, 27)
    assert approved.end_date == date(2031, 1, 2)
    assert approved.timezone == "Asia/Seoul"
    assert approved.live_request_allowed is False
    assert approved.status == "PREFLIGHT_VALIDATED"
    assert profile in approved.input_text
    assert "최대 3건" in approved.input_text
    assert product().valid_demo_plan(approved, synthetic=True)


@pytest.mark.parametrize("instant,end", [
    (datetime(2031, 1, 1, 14, 59, tzinfo=timezone.utc), date(2031, 1, 1)),
    (datetime(2031, 1, 1, 15, 0, tzinfo=timezone.utc), date(2031, 1, 2)),
])
def test_demo_calendar_uses_seoul_midnight(instant, end):
    approved = product().build_demo_plan(
        config=product().DemoSearchConfig(profile="BEAUTY"), execution_at=instant,
    )
    assert approved.end_date == end
    assert (approved.end_date - approved.start_date).days == 6


@pytest.mark.parametrize("profile", PROFILES[:-1])
def test_legacy_configs_still_reject_other_categories(profile):
    from app.responses_web_search import gate_d_preflight
    from app.responses_web_search.types import SearchRunConfig

    with pytest.raises(gate_d_preflight.GateDPreflightError):
        gate_d_preflight.GateDConfig(profile=profile)
    with pytest.raises(ValueError):
        SearchRunConfig(profile=profile)


@pytest.mark.parametrize("changes", [
    {"profile": "OTHER"}, {"profile": "fashion"}, {"profile": None},
    {"profile": []}, {"model": "other"}, {"lookback_days": 8},
    {"max_candidates": 4}, {"max_candidates": True}, {"max_tool_calls": 2},
    {"max_tool_calls": True}, {"max_retries": 1}, {"timeout": 60},
    {"max_output_tokens": 4096.0}, {"store": True}, {"stream": True},
])
def test_unapproved_config_is_rejected(changes):
    with pytest.raises(ValueError, match="invalid demo search configuration"):
        product().DemoSearchConfig(**({"profile": "FASHION"} | changes))


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("field,value", [
    ("input_text", "changed prompt"), ("start_date", date(2030, 12, 26)),
    ("end_date", date(2031, 1, 3)), ("live_request_allowed", True),
    ("status", "APPROVED"), ("timezone", "UTC"),
])
def test_tampered_plan_blocks_dispatch(endpoint, field, value):
    approved = deepcopy(plan())
    object.__setattr__(approved, field, value)
    result = invoke(endpoint, plan=approved)
    assert result["status"] == "BLOCKED_CONFIG"
    assert endpoint.calls == []


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("field", ["config", "input_text", "start_date"])
def test_incomplete_plan_blocks_dispatch(endpoint, field):
    approved = deepcopy(plan())
    object.__delattr__(approved, field)
    assert product().valid_demo_plan(approved, synthetic=True) is False
    assert invoke(endpoint, plan=approved)["status"] == "BLOCKED_CONFIG"
    assert endpoint.calls == []


@pytest.mark.usefixtures("no_dispatch")
def test_cross_category_or_mutated_config_cannot_relabel_request(endpoint):
    approved = replace(plan(), config=product().DemoSearchConfig(profile="BEAUTY"))
    assert invoke(endpoint, plan=approved)["status"] == "BLOCKED_CONFIG"
    approved = deepcopy(plan())
    object.__setattr__(approved.config, "max_retries", 1)
    assert invoke(endpoint, plan=approved)["status"] == "BLOCKED_CONFIG"


@pytest.mark.usefixtures("no_dispatch")
def test_old_real_plan_and_wrong_plan_type_are_blocked(endpoint):
    assert invoke(endpoint, http_transport=None)["status"] == "BLOCKED_CONFIG"
    assert invoke(endpoint, plan=object())["status"] == "BLOCKED_CONFIG"
    with pytest.raises(ValueError):
        product().build_demo_plan(
            config=product().DemoSearchConfig(profile="GAME"),
            execution_at=datetime(2031, 1, 2),
        )


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("changes", [
    {"execute_live": False}, {"interactive": False}, {"confirmation": "wrong"},
    {"confirmation": PHRASE + " "}, {"api_key": None}, {"api_key": "bad\nkey"},
])
def test_service_approval_and_key_boundaries(endpoint, changes):
    result = invoke(endpoint, **changes)
    assert result["status"] in {"LIVE_NOT_AUTHORIZED", "BLOCKED_CONFIG"}
    assert endpoint.calls == []


@pytest.mark.parametrize("profile", PROFILES)
def test_real_sdk_single_request_uses_actual_profile(
    endpoint, profile, caplog, capsys,
):
    endpoint.payload = payload_for("ready")
    part = endpoint.payload["output"][-1]["content"][0]
    values = json.loads(part["text"])
    values["candidates"][0]["proposed_category_ref"] = "FAKE_MODEL_CATEGORY"
    part["text"] = json.dumps(values)
    original = deepcopy(endpoint.payload)
    approved = plan(profile)
    result = invoke(endpoint, plan=approved)
    assert result["status"] == "PREVIEW_READY", result
    assert_request(endpoint, approved)
    assert result["search_profile"] == profile
    assert result["request_max_tool_calls"] == 1
    assert result["citation_validation"] == "MATCHED"
    for candidate in result["candidates"]:
        assert candidate["candidate_index"] == 0
        assert candidate["citation_validation"] == "MATCHED"
        assert candidate["proposed_category_ref"] == profile
        assert candidate["review_status"] == "REVIEW_REQUIRED"
        assert candidate["publication_status"] == "NOT_FOR_PUBLICATION"
        assert candidate["publish_authorization"] == "NONE"
        assert candidate["independent_source_verified"] is False
    assert endpoint.payload == original
    captured = capsys.readouterr()
    visible = json.dumps(result) + caplog.text + captured.out + captured.err
    assert API_KEY not in visible
    assert MARKER not in visible
    assert approved.input_text not in visible
    assert "FAKE_MODEL_CATEGORY" not in visible


@pytest.mark.parametrize("case,expected", [
    ("ready", "PREVIEW_READY"), ("discarded", "NO_VALID_CANDIDATES"),
    ("empty", "EMPTY_RESULT"), ("bad-json", "INVALID_OR_INCOMPLETE_RESPONSE"),
])
@pytest.mark.parametrize("d2_state", [None, "searching", "failed", "completed"])
def test_d2_and_citation_results_are_preserved(endpoint, case, expected, d2_state):
    endpoint.payload = payload_for(case)
    if d2_state is not None:
        pending = deepcopy(endpoint.payload["output"][0])
        pending.update(id="ws_pending", status=d2_state)
        endpoint.payload["output"].insert(1, pending)
    original = deepcopy(endpoint.payload)
    result = invoke(endpoint)
    if d2_state in {"failed", "completed"}:
        expected = "INVALID_OR_INCOMPLETE_RESPONSE"
    elif d2_state == "searching" and case == "ready":
        expected = "PARTIAL_PREVIEW_READY"
    assert result["status"] == expected
    assert len(endpoint.calls) == 1
    assert endpoint.payload == original
    if d2_state == "searching" and case != "bad-json":
        assert result["response_validation"] == "PARTIAL"
        assert result["tool_calls_observed"] == 2
    if case == "discarded" and d2_state in {None, "searching"}:
        assert result["citation_validation"] == "MISMATCH"
        assert result["issues"] == [
            {"candidate_index": 0, "code": "CITATION_URL_MISMATCH"},
        ]
        assert result["review_only_candidates"][0]["rejection_reason"] == (
            "CITATION_URL_MISMATCH"
        )
        assert result["review_only_candidates"][0]["proposed_category_ref"] == "FASHION"
        assert result["review_only_candidates"][0]["citation_validation"] == "MISMATCH"


def test_original_indices_survive_mismatch_and_duplicate_filtering(endpoint):
    endpoint.payload = payload_for("ready")
    part = endpoint.payload["output"][-1]["content"][0]
    first = json.loads(part["text"])["candidates"][0]
    mismatch = dict(first, topic_draft="Review only",
                    source_url="https://example.org/mismatch")
    part["text"] = json.dumps({"candidates": [mismatch, first, first]})
    result = invoke(endpoint, plan=plan("GAME"))
    assert len(endpoint.calls) == 1
    assert result["citation_validation"] == "PARTIAL"
    assert [item["candidate_index"] for item in result["candidates"]] == [1]
    assert result["candidates"][0]["citation_validation"] == "MATCHED"
    assert result["review_only_candidates"][0]["candidate_index"] == 0
    assert result["review_only_candidates"][0]["citation_validation"] == "MISMATCH"
    assert result["issues"] == [
        {"candidate_index": 0, "code": "CITATION_URL_MISMATCH"},
        {"candidate_index": 2, "code": "DUPLICATE_CANDIDATE"},
    ]


@pytest.mark.parametrize("count", [3, 4])
def test_candidate_limit_is_not_silently_truncated(endpoint, count):
    endpoint.payload = payload_for("ready")
    part = endpoint.payload["output"][-1]["content"][0]
    first = json.loads(part["text"])["candidates"][0]
    candidates = [dict(first, topic_draft=f"Topic {index}",
                       source_url=f"https://example.org/source/{index}")
                  for index in range(count)]
    part["text"] = json.dumps({"candidates": candidates})
    part["annotations"] = [dict(part["annotations"][0], url=item["source_url"])
                           for item in candidates]
    result = invoke(endpoint)
    assert len(endpoint.calls) == 1
    assert len(result["candidates"]) == (3 if count == 3 else 0)
    if count == 4:
        assert result["reason_codes"] == ["CANDIDATE_LIMIT_EXCEEDED"]


@pytest.mark.parametrize("failure", ["timeout", "429", "503", "model"])
def test_failures_never_retry(endpoint, failure):
    endpoint.payload = payload_for("ready")
    if failure == "timeout":
        endpoint.transport_error = httpx2.ReadTimeout
    elif failure == "model":
        endpoint.payload["model"] = "unapproved-model"
    else:
        endpoint.status = int(failure)
    result = invoke(endpoint)
    assert result["candidates"] == []
    assert len(endpoint.calls) == 1
    assert API_KEY not in json.dumps(result)


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("profile", PROFILES)
def test_cli_offline_plan(endpoint, profile):
    code, stdout, stderr = cli(endpoint, ["--profile", profile])
    assert code == 0
    assert not stderr
    assert json.loads(stdout)["config"]["profile"] == profile
    assert endpoint.calls == []


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("args", [
    [], ["--execute-live"], ["--profile", "OTHER"],
    ["--profile", "FASHION", "--review-local"],
    ["--profile", "FASHION", "--execute-live", "--execute-live"],
])
def test_cli_requires_explicit_profile_and_known_grammar(endpoint, args):
    code, _, _ = cli(endpoint, args)
    assert code == 1
    assert endpoint.calls == []


@pytest.mark.usefixtures("no_dispatch")
@pytest.mark.parametrize("stdin,stdout", [
    (Terminal(PHRASE + "\n", tty=False), Terminal()),
    (Terminal(PHRASE + "\n"), Terminal(tty=False)),
    (Terminal("wrong\n"), Terminal()),
    (Terminal(PHRASE + " \n"), Terminal()),
])
def test_cli_tty_and_confirmation_before_key_or_dispatch(endpoint, stdin, stdout):
    code, _, _ = cli(endpoint, ["--profile", "GAME", "--execute-live"],
                     stdin=stdin, stdout=stdout)
    assert code == 1
    assert endpoint.calls == []


@pytest.mark.usefixtures("no_dispatch")
def test_cli_readiness_has_no_paid_authorization(endpoint, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    code, stdout, _ = cli(endpoint, ["--check-readiness"])
    result = json.loads(stdout)
    assert code == 0
    assert result["paid_call_authorized"] is False
    assert result["api_key_configured"] is True
    assert API_KEY not in stdout


@pytest.mark.parametrize("review_local", [False, True])
def test_cli_live_mock_and_local_review_visibility(endpoint, monkeypatch, review_local):
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    endpoint.payload = payload_for("discarded")
    args = ["--profile", "FOOD", "--execute-live"]
    if review_local:
        args.append("--review-local")
    code, stdout, _ = cli(endpoint, args)
    result = json.loads(stdout)
    assert code == 0
    assert len(endpoint.calls) == 1
    assert result["search_profile"] == "FOOD"
    assert result["review_only_candidate_count"] == 1
    assert ("review_only_candidates" in result) is review_local


@pytest.mark.usefixtures("no_dispatch")
def test_cli_cannot_inject_synthetic_date_into_real_execution(endpoint):
    code, _, _ = cli(
        endpoint, ["--profile", "GAME", "--execute-live"], http_transport=None,
    )
    assert code == 1
    assert endpoint.calls == []
