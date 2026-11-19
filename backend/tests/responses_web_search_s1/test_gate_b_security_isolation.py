"""Gate B E-03/E-04a/E-04b/E-06 synthetic security review.

E-03 mapping (no duplicate immutability-only tests): Phase 1 run_s1() deep-copies
every supplied response and compares after the full service call. P-01 covers
success, P-08 Normalizer rejection, P-04 in preview_remaining covers Parser
failure. Gate A normalize() also compares deep copies and forbids S0 calls.
New E-04 cases reuse these same real pipeline/Mock/immutability helpers.

E-06 mapping: every service case runs under no_external_io's zero-attempt
teardown check and the collection import guard. The probes below establish
that those real Python boundaries are blocked BEFORE I/O/module execution.
Probes are deliberate guard checks, not product calls or DB DML/Writer spies.
Current S1/Normalizer/Parser/Validator have no logging, DB, Redis, Writer or
publication call site. No fictitious persistence API is patched. Unconnected
DB/Redis/Writer integration and future logging sinks remain NOT VERIFIED.
No claim is made about a complete OS sandbox or all possible I/O mechanisms.

Only synthetic markers are used. Environment replacement contains no real
environment values and keeps secret reads forbidden, including swallowed reads.
E-04c internal candidate text and E-10 CLI escaping are outside this review.
Gate C/D, G5/G6 HOLD and P4 NOT FROZEN remain unchanged.
"""

import importlib
import io
import json
import logging
import os
import socket
import subprocess
from collections.abc import Mapping

import pytest

from .fixtures import content, response
from .test_gate_b_adapter_errors import assert_read_only
from .test_gate_b_preview import (
    assert_flow,
    assert_preview,
    pipeline as pipeline,
    run_s1,
)
from .test_gate_b_preview_remaining import assert_parser_short_circuit


class SyntheticEnvironment(Mapping):
    """In-memory secrets only; preserve the S1 prohibition on reading secrets."""

    def __init__(self, values):
        self._values = values
        self.attempts = []

    def __getitem__(self, key):
        if key in self._values:
            self.attempts.append("secret-read")
            raise AssertionError("S1 synthetic secret environment read forbidden")
        raise KeyError(key)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


def assert_no_marker(markers, preview, pipeline, caplog, capsys):
    captured = capsys.readouterr()
    # Raw parser_input intentionally carries candidate JSON to S0; it is not a
    # public diagnostic. Inspect actual safe diagnostic representations instead.
    diagnostics = repr(pipeline.normalization_results)
    diagnostics += repr([
        (result.execution_evidence, result.reason_codes, result.citation_trace)
        for result in pipeline.normalization_results
    ])
    surfaces = [
        json.dumps(preview), json.dumps(preview["reason_codes"]),
        json.dumps(preview["issues"]), diagnostics, caplog.text,
        repr([(record.msg, record.args) for record in caplog.records]),
        captured.out, captured.err,
    ]
    for marker in markers:
        assert all(marker not in surface for surface in surfaces)


@pytest.mark.parametrize("path", ["normal", "timeout"])
def test_e04a_environment_secrets_are_not_inputs_or_outputs(
    path, pipeline, monkeypatch, caplog, capsys,
):
    caplog.set_level(logging.DEBUG)
    markers = ("SYNTHETIC_E04A_API_KEY", "SYNTHETIC_E04A_AUTHORIZATION")
    environment = SyntheticEnvironment({
        "OPENAI_API_KEY": markers[0],
        "AUTHORIZATION": "Bearer " + markers[1],
    })
    payload = response() if path == "normal" else None
    error = TimeoutError("synthetic timeout") if path == "timeout" else None
    # Do not setenv/patch.dict the real environment: even reading it is guarded.
    with monkeypatch.context() as patch:
        patch.setattr(os, "environ", environment)
        preview = run_s1(pipeline, payload=payload, error=error)
    assert environment.attempts == []
    if path == "normal":
        assert_flow(pipeline, payload, normalized=True)
        assert_preview(preview, status="PREVIEW_READY", search="CONFIRMED",
                       validation="VALID", calls=1)
        assert len(preview["candidates"]) == 1
    else:
        assert_read_only(pipeline)
        assert_preview(preview, status="UPSTREAM_ERROR", search="UNKNOWN",
                       validation="NOT_EVALUATED", calls=None)
        assert preview["candidates"] == []
    assert preview["issues"] == preview["reason_codes"] == []
    assert_no_marker(markers, preview, pipeline, caplog, capsys)


@pytest.mark.parametrize("path", ["refusal", "invalid-json"])
def test_e04b_failed_response_text_is_not_exposed_or_partially_returned(
    path, pipeline, caplog, capsys,
):
    caplog.set_level(logging.DEBUG)
    marker = "SYNTHETIC_E04B_" + path.upper() + "_PRIVATE_MARKER"
    payload = response()
    if path == "refusal":
        # Keep the valid candidate/URL too: partial success must not escape.
        payload["output"][1]["content"].append({
            "type": "refusal", "refusal": marker,
        })
    else:
        content(payload)["text"] += "\n" + marker
    assert marker in json.dumps(payload)
    preview = run_s1(pipeline, payload=payload)
    if path == "refusal":
        assert_flow(pipeline, payload, normalized=False)
    else:
        assert_parser_short_circuit(pipeline, payload, calls=1, searches=1)
    assert_preview(preview, status="INVALID_OR_INCOMPLETE_RESPONSE",
                   search="CONFIRMED", validation="INVALID", calls=1)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == ["RESPONSE_STRUCTURE_INVALID"]
    assert_no_marker([marker], preview, pipeline, caplog, capsys)


@pytest.mark.parametrize("module", [
    "app.db.session", "app.repositories.trend_repository", "sqlalchemy",
])
def test_e06_existing_database_import_boundaries_are_blocked(module, isolated_session):
    with pytest.raises(AssertionError, match="S1 forbidden import"):
        importlib.import_module(module)


@pytest.mark.parametrize("operation", ["network", "process", "open", "io", "os"])
def test_e06_io_guards_block_before_external_effect(operation, no_external_io):
    # Declare exactly one intentional blocked probe; service tests declare none.
    no_external_io.append("blocked")
    with pytest.raises(AssertionError, match="S1 external I/O is forbidden"):
        if operation == "network":
            socket.create_connection(("synthetic.example.test", 443))
        elif operation == "process":
            subprocess.Popen(["must-not-start-s1"])
        elif operation == "open":
            open("must-not-be-created-s1.txt", "w")
        elif operation == "io":
            io.open("must-not-be-created-s1.txt", "w")
        else:
            os.open("must-not-be-created-s1.txt", os.O_WRONLY | os.O_CREAT)
