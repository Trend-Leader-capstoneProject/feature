"""Scheduler state and request delay checks; no operational server or live HTTP."""

import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.trend_collection.rate_limit import retry_deadline
from scripts.auto_supply_control import (
    INTERVAL,
    choose_source,
    cycle,
    load_state,
    next_state,
)

NOW = 100000
READY = {'pending': False, 'not_before': 0, 'rate_failures': 0}


def _profile(*source_ids):
    entries = tuple(SimpleNamespace(source_id=value) for value in source_ids)

    def source(source_id):
        return next(item for item in entries if item.source_id == source_id)

    return SimpleNamespace(collector_uid=101, writer_uid=102,
                           sources=entries, source=source)


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
    profile = _profile('godotengine/godot-builds')
    envelope = {'source_id': 'godotengine/godot-builds', 'preview': {}}
    child = Mock(side_effect=[(0, envelope), (0, {'status': 'COMMITTED'})])
    assert cycle(profile, path, READY, child=child, clock=lambda: NOW) == {
        'status': 'COMMITTED',
    }
    assert child.call_args_list[0].args == (101, 'collect')
    assert child.call_args_list[0].kwargs == {
        'source_id': 'godotengine/godot-builds',
    }
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
    profile = _profile('godotengine/godot-builds')

    def crash(*args, **kwargs):
        assert kwargs['source_id'] == 'godotengine/godot-builds'
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


def test_legacy_scheduler_state_acceptance_and_strict_rotation_field(tmp_path):
    path = tmp_path / 'scheduler-state.json'
    assert load_state(path, lambda _: dict(READY)) == READY
    valid = {**READY, 'last_completed_source_id': 'godotengine/godot-builds'}
    assert load_state(path, lambda _: valid) == valid
    for value in (None, True, '', 'bad source', '../unsafe', 500):
        with pytest.raises(RuntimeError, match='SCHEDULER_STATE_INVALID'):
            load_state(path, lambda _: {
                **READY, 'last_completed_source_id': value,
            })
    with pytest.raises(RuntimeError, match='SCHEDULER_STATE_INVALID'):
        load_state(path, lambda _: {**READY, 'unexpected': 1})


def test_round_robin_by_approved_source_ids():
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    assert choose_source(profile, READY).source_id == 'godotengine/godot-builds'
    assert choose_source(profile, {
        **READY, 'last_completed_source_id': 'godotengine/godot-builds',
    }).source_id == 'igdb:visits'
    assert choose_source(profile, {
        **READY, 'last_completed_source_id': 'igdb:visits',
    }).source_id == 'godotengine/godot-builds'
    assert choose_source(profile, {
        **READY, 'last_completed_source_id': 'archived:source',
    }).source_id == 'godotengine/godot-builds'


@pytest.mark.parametrize('status', ['COMMITTED', 'SKIP_EXISTING_RELEASE'])
def test_success_advances_only_explicit_selected_source(status):
    done = next_state({'status': status}, NOW, READY, writer=True,
                      source_id='godotengine/godot-builds')
    assert done == {
        **READY, 'not_before': NOW + INTERVAL,
        'last_completed_source_id': 'godotengine/godot-builds',
    }
    assert next_state({'status': status}, NOW, READY, writer=True) == {
        **READY, 'not_before': NOW + INTERVAL,
    }


def test_failures_preserve_rotation_and_cooldown():
    state = {
        **READY, 'last_completed_source_id': 'godotengine/godot-builds',
    }
    limited = next_state({
        'status': 'HOLD', 'reason': 'RATE_LIMITED',
        'retry_not_before': NOW + INTERVAL * 3,
    }, NOW, state, source_id='igdb:visits')
    assert limited['last_completed_source_id'] == 'godotengine/godot-builds'
    assert limited['not_before'] == NOW + INTERVAL * 3
    unknown = next_state({'status': 'HOLD'}, NOW, state, writer=True,
                         source_id='igdb:visits')
    assert unknown['pending'] is True
    assert unknown['last_completed_source_id'] == 'godotengine/godot-builds'


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_cycle_rotates_two_sources_after_verified_writer_success(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    seen = []

    def child(uid, role, envelope=None, *, source_id=None):
        if role == 'collect':
            seen.append(source_id)
            return 0, {'source_id': source_id, 'preview': {}}
        assert uid == profile.writer_uid
        return 0, {'status': 'COMMITTED'}

    first = cycle(profile, path, READY, child=child, clock=lambda: NOW)
    assert first['status'] == 'COMMITTED'
    state = json.loads(path.read_text())
    assert state['not_before'] == NOW + INTERVAL
    assert state['last_completed_source_id'] == 'godotengine/godot-builds'
    assert cycle(profile, path, state, child=child,
                 clock=lambda: NOW)['reason'] == 'SCHEDULER_COOLDOWN'
    second = cycle(profile, path, state, child=child,
                   clock=lambda: NOW + INTERVAL)
    assert second['status'] == 'COMMITTED'
    state = json.loads(path.read_text())
    assert state['last_completed_source_id'] == 'igdb:visits'
    assert seen == ['godotengine/godot-builds', 'igdb:visits']


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_wrong_collector_source_latches_pending(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    calls = Mock(return_value=(0, {'source_id': 'igdb:visits', 'preview': {}}))
    with pytest.raises(RuntimeError, match='COLLECTOR_SOURCE_MISMATCH'):
        cycle(profile, path, READY, child=calls, clock=lambda: NOW)
    assert json.loads(path.read_text())['pending'] is True
    assert calls.call_count == 1


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_wrong_writer_status_latches_pending(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    calls = Mock(side_effect=[
        (0, {'source_id': 'godotengine/godot-builds', 'preview': {}}),
        (2, {'status': 'COMMITTED'}),
    ])
    with pytest.raises(RuntimeError, match='WRITER_OUTCOME_MISMATCH'):
        cycle(profile, path, READY, child=calls, clock=lambda: NOW)
    assert json.loads(path.read_text())['pending'] is True
    assert calls.call_count == 2


@pytest.mark.skipif(os.name != 'posix', reason='Linux child process contract only')
def test_child_passes_explicit_source_id_and_rejects_mismatch(monkeypatch):
    import pwd

    from scripts import auto_supply_control as control

    monkeypatch.setattr(pwd, 'getpwuid', lambda _: SimpleNamespace(
        pw_name='trend-collector', pw_gid=200,
    ))
    runner = Mock(return_value=SimpleNamespace(
        returncode=0,
        stdout=b'{"source_id":"godotengine/godot-builds","preview":{}}',
    ))
    monkeypatch.setattr(control.subprocess, 'run', runner)
    code, envelope = control.run_child(
        101, 'collect', source_id='godotengine/godot-builds',
    )
    assert code == 0 and envelope['source_id'] == 'godotengine/godot-builds'
    args = runner.call_args.args[0]
    assert args[-2:] == ['--source-id', 'godotengine/godot-builds']
    runner.return_value.stdout = b'{"source_id":"igdb:visits","preview":{}}'
    with pytest.raises(RuntimeError, match='CHILD_OUTCOME_UNKNOWN'):
        control.run_child(101, 'collect', source_id='godotengine/godot-builds')
