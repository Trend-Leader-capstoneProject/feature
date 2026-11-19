"""E-02 Red: user-adopted S1 synthetic Adapter failure contract.

Internal binding: s1_service.SyntheticUpstreamError(kind=...) is an Exception
with string kind in {401, 403, 429, 5xx}; invalid kind raises ValueError on
construction, consistent with existing internal configuration validation.
This is not an SDK exception contract and does not reuse S0's fixture error.
Only runtime lookup is used: missing error type is Red, not collection failure.
No substitute error class, skip or xfail may mask missing product support.

Exception.args is populated with synthetic private text after construction to
test non-disclosure without assuming a message/SDK/HTTP constructor parameter.
P-02/E-01 timeout coverage remains in test_gate_b_preview.py; unexpected-error
tests below guard against broad except Exception swallowing programming errors.
Gate C/D, G5/G6 HOLD and P4 NOT FROZEN remain unchanged.
"""

import importlib
import json

import pytest

from .test_gate_b_preview import (
    assert_preview,
    pipeline as pipeline,
    run_s1,
)


def synthetic_error_type():
    module = importlib.import_module("app.responses_web_search.s1_service")
    # Do not catch AttributeError: it identifies the absent internal error type.
    error_type = module.SyntheticUpstreamError
    assert issubclass(error_type, Exception)
    return error_type


def assert_read_only(pipeline):
    pipeline.events.read.assert_called_once_with()
    pipeline.normalize.assert_not_called()
    pipeline.parse.assert_not_called()
    pipeline.validate.assert_not_called()
    pipeline.fixture_service.assert_not_called()
    assert [event[0] for event in pipeline.events.mock_calls] == ["read"]


@pytest.mark.parametrize("kind", ["401", "403", "429", "5xx"])
def test_e02_upstream_errors_are_unknown_without_retry_or_disclosure(kind, pipeline):
    marker = "SYNTHETIC_E02_PRIVATE_MARKER"
    errors = []

    def fail_read():
        # run_s1 reloads S1 to refresh spies: construct the error afterwards so
        # its class identity matches the service's current exception handler.
        error = synthetic_error_type()(kind=kind)
        assert error.kind == kind
        error.args = (f"{marker}: synthetic upstream failure detail for {kind}",)
        assert marker in str(error)
        errors.append(error)
        raise error

    preview = run_s1(pipeline, error=fail_read)
    error, = errors
    assert_read_only(pipeline)
    assert_preview(preview, status="UPSTREAM_ERROR", search="UNKNOWN",
                   validation="NOT_EVALUATED", calls=None)
    assert preview["candidates"] == []
    assert preview["issues"] == []
    assert preview["reason_codes"] == []
    serialized = json.dumps(preview)
    assert marker not in serialized
    assert str(error) not in serialized


@pytest.mark.parametrize("kind", [
    "", "400", "500", "timeout", " 401", "401 ",
    401, None, True, [], {}, "SYNTHETIC_INVALID_KIND_PRIVATE_MARKER",
], ids=[
    "empty", "unsupported-4xx", "numeric-5xx-string", "timeout-is-separate",
    "leading-space", "trailing-space", "integer", "null", "boolean",
    "list", "dict", "private-text",
])
def test_e02_invalid_kind_is_rejected_at_construction(kind, isolated_session):
    error_type = synthetic_error_type()
    with pytest.raises(ValueError):
        error_type(kind=kind)


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_e02_unexpected_adapter_exception_is_not_swallowed(error_type, pipeline):
    error = error_type("SYNTHETIC_UNEXPECTED_ADAPTER_ERROR")
    with pytest.raises(error_type) as caught:
        run_s1(pipeline, error=error)
    assert caught.value is error
    assert_read_only(pipeline)
