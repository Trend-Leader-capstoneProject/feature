"""Scheduler state and request delay checks; no operational server or live HTTP."""

import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.rate_limit import retry_deadline
from scripts.auto_supply_control import INTERVAL, cycle, next_state

NOW = 100000
READY = {'pending': False, 'not_before': 0, 'rate_failures': 0}


@pytest.mark.parametrize(('headers', 'expected'), [
    ({}, NOW + 60),
    ({'Retry-After': '72000'}, NOW + 72000),
    ({'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '150000'}, 150001),
    ({'X-RateLimit-Remaining': '0'}, None),
    ({'Retry-After': 'invalid'}, None),
    ({'Retry-After': 'Thu, 01 Jan 1970 00:00:00 GMT'}, NOW + 60),
])
def test_retry_deadline(headers, expected):
    assert retry_deadline(headers, NOW) == expected


def test_backoff_never_shortens_header():
    limited = {'status': 'HOLD', 'reason': 'RATE_LIMITED',
               'retry_not_before': NOW + 72000}
    first = next_state(limited, NOW, READY)
    assert first == {'pending': False, 'not_before': NOW + 72000, 'rate_failures': 1}
    second = next_state({**limited, 'retry_not_before': NOW}, NOW, first)
    assert second['not_before'] == NOW + INTERVAL * 2
    assert next_state(limited, NOW, second)['pending']
    assert next_state({**limited, 'retry_not_before': None}, NOW, READY)['pending']


def test_unknown_writer_halts():
    assert next_state({'status': 'HOLD'}, NOW, READY, writer=True)['pending']


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_cycle_orders_children_and_blocks_reentry(tmp_path):
    path = tmp_path / 'state.json'
    profile = SimpleNamespace(collector_uid=101, writer_uid=102)
    envelope = {'source_id': 'example', 'preview': {}}
    child = Mock(side_effect=[(0, envelope), (0, {'status': 'COMMITTED'})])
    assert cycle(profile, path, READY, child=child, clock=lambda: NOW) == {
        'status': 'COMMITTED',
    }
    assert child.call_args_list[0].args == (101, 'collect')
    assert child.call_args_list[1].args == (102, 'write', envelope)
    state = json.loads(path.read_text())
    assert state['not_before'] == NOW + INTERVAL
    child.reset_mock()
    assert cycle(profile, path, state, child=child, clock=lambda: NOW)['reason'] == (
        'SCHEDULER_COOLDOWN'
    )
    child.assert_not_called()


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_crash_persists_pending_before_request(tmp_path):
    path = tmp_path / 'state.json'
    profile = SimpleNamespace(collector_uid=101, writer_uid=102)

    def crash(*args):
        assert json.loads(path.read_text())['pending'] is True
        raise RuntimeError('crash')

    with pytest.raises(RuntimeError, match='crash'):
        cycle(profile, path, READY, child=crash, clock=lambda: NOW)
    state = json.loads(path.read_text())
    child = Mock()
    assert cycle(profile, path, state, child=child, clock=lambda: NOW)['reason'] == (
        'SCHEDULER_INVESTIGATION_REQUIRED'
    )
    child.assert_not_called()
