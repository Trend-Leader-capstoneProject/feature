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


DB_CONNECT_HOLD = {
    'status': 'HOLD', 'reason': 'WRITER_DB_CONNECT_FAILED',
    'db_error_code': 2003, 'candidate_identity': 'igdb-game:87622',
    'profile': 'AUTO-TREND-MVP',
}


def test_db_connect_retry_budget_preserves_cursors_and_deadline(tmp_path):
    state = {
        **READY, 'last_completed_source_id': 'godotengine/godot-builds',
        'igdb_last_game_id': 87622, 'interest_last_case_key': 'a' * 64,
        'related_news_rate_failures': 1, 'rate_failures': 1,
    }
    for failures in range(1, 4):
        now = NOW + (failures - 1) * INTERVAL
        state = next_state(
            DB_CONNECT_HOLD, now, state, writer=True, source_id='igdb:visits',
        )
        state = load_state(tmp_path, lambda _: json.loads(json.dumps(state)))
        assert state['pending'] is (failures == 3)
        assert state['not_before'] == now + INTERVAL
        assert state['db_connect_failures'] == failures
        assert state['last_completed_source_id'] == 'godotengine/godot-builds'
        assert state['igdb_last_game_id'] == 87622
        assert state['interest_last_case_key'] == 'a' * 64
        assert state['related_news_rate_failures'] == 1
        assert state['rate_failures'] == 1


@pytest.mark.parametrize('value', [0, 4, True, '1', None, 3])
def test_db_connect_counter_rejects_invalid_ready_state(tmp_path, value):
    with pytest.raises(RuntimeError, match='SCHEDULER_STATE_INVALID'):
        load_state(tmp_path, lambda _: {**READY, 'db_connect_failures': value})


@pytest.mark.parametrize('changes', [
    {'reason': 'WRITER_COMMIT_FAILED'},
    {'reason': 'WRITER_JOURNAL_CLAIM_FAILED'},
    {'db_error_code': 1045}, {'db_error_code': '2003'},
    {'db_error_code': True}, {'candidate_identity': None},
    {'related_news_status': 'EMPTY'}, {'retry_not_before': NOW + 72000},
    {'profile': 'UNAPPROVED'}, {'profile': None},
])
def test_only_exact_preclaim_hold_can_retry(changes):
    state = next_state({**DB_CONNECT_HOLD, **changes}, NOW, READY, writer=True)
    assert state['pending'] is True
    assert 'db_connect_failures' not in state


def test_db_connect_missing_cli_profile_halts():
    result = {key: value for key, value in DB_CONNECT_HOLD.items()
              if key != 'profile'}
    state = next_state(result, NOW, READY, writer=True)
    assert state['pending'] is True
    assert 'db_connect_failures' not in state


def test_db_connect_budget_is_not_reset_by_other_failure():
    previous = {**READY, 'db_connect_failures': 2}
    state = next_state({'status': 'HOLD'}, NOW, previous, writer=True)
    assert state['pending'] is True
    assert state['db_connect_failures'] == 2


@pytest.mark.parametrize('status', [
    'COMMITTED', 'SKIP_EXISTING_RELEASE', 'SKIP_NO_CANDIDATE',
])
def test_terminal_outcome_clears_db_connect_budget(status):
    previous = {**READY, 'db_connect_failures': 2}
    empty = status == 'SKIP_NO_CANDIDATE'
    state = next_state(
        {'status': status}, NOW, previous, writer=not empty, no_candidate=empty,
    )
    assert state['pending'] is False
    assert 'db_connect_failures' not in state


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_db_connect_retries_same_source_then_halts(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    state = {**READY, 'last_completed_source_id': 'godotengine/godot-builds'}
    envelope = {
        'source_id': 'igdb:visits',
        'preview': {'candidate_identity': 'igdb-game:87622'},
    }
    for failures in range(1, 4):
        now = NOW + (failures - 1) * INTERVAL
        child = Mock(side_effect=[(0, envelope), (2, DB_CONNECT_HOLD)])
        result = cycle(profile, path, state, child=child, clock=lambda: now)
        assert child.call_args_list[0].kwargs == {'source_id': 'igdb:visits'}
        assert child.call_count == 2
        state = load_state(path, lambda p: json.loads(p.read_text()))
        assert result['db_connect_failures'] == failures
        assert state['pending'] is (failures == 3)
        assert result.get('retry_not_before') == (
            now + INTERVAL if failures < 3 else None
        )
        child.reset_mock()
        blocked = cycle(profile, path, state, child=child, clock=lambda: now)
        assert blocked['reason'] == (
            'SCHEDULER_INVESTIGATION_REQUIRED' if failures == 3
            else 'SCHEDULER_COOLDOWN'
        )
        child.assert_not_called()


@pytest.mark.parametrize(('source', 'preview', 'identity'), [
    ('godotengine/godot-builds',
     {'candidate_identity': 'github-release:godotengine/godot-builds:42'},
     'github-release:godotengine/godot-builds:42'),
    ('searchapi-kr-interest', {'case_key': 'a' * 64},
     'searchapi-interest:' + 'a' * 64),
    ('searchapi-kr-reviewed-news', {'case_key': 'b' * 64},
     'searchapi-event:' + 'b' * 64),
])
@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_db_connect_retry_confirms_each_source_identity(
    tmp_path, source, preview, identity,
):
    path = tmp_path / 'state.json'
    profile = _profile(source)
    envelope = {'source_id': source, 'preview': preview}
    hold = {**DB_CONNECT_HOLD, 'candidate_identity': identity}
    child = Mock(side_effect=[(0, envelope), (2, hold)])
    result = cycle(profile, path, READY, child=child, clock=lambda: NOW)
    assert result['db_connect_failures'] == 1
    assert result['retry_not_before'] == NOW + INTERVAL
    assert json.loads(path.read_text())['pending'] is False


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_db_connect_retry_rejects_mismatched_identity(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('igdb:visits')
    envelope = {
        'source_id': 'igdb:visits',
        'preview': {'candidate_identity': 'igdb-game:42'},
    }
    child = Mock(side_effect=[(0, envelope), (2, DB_CONNECT_HOLD)])
    with pytest.raises(RuntimeError, match='DB_CONNECT_RETRY_IDENTITY_UNCONFIRMED'):
        cycle(profile, path, READY, child=child, clock=lambda: NOW)
    assert json.loads(path.read_text())['pending'] is True


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
            preview = ({'candidate_identity': 'igdb-game:87622'}
                       if source_id == 'igdb:visits' else {})
            return 0, {'source_id': source_id, 'preview': preview}
        assert uid == profile.writer_uid
        if envelope['source_id'] == 'igdb:visits':
            return 0, {'status': 'COMMITTED',
                       'candidate_identity': 'igdb-game:87622'}
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
    assert state['igdb_last_game_id'] == 87622
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


@pytest.mark.parametrize('status', ['COMMITTED', 'SKIP_EXISTING_RELEASE'])
def test_igdb_cursor_advances_only_after_verified_writer(status):
    profile = _profile('igdb:visits')
    state = {**READY, 'last_completed_source_id': 'igdb:visits',
             'igdb_last_game_id': 87622}
    result = next_state(
        {'status': status}, NOW, state, writer=True,
        source_id='igdb:visits', game_id=115,
    )
    assert result['igdb_last_game_id'] == 115
    assert result['not_before'] == NOW + INTERVAL
    assert result['last_completed_source_id'] == 'igdb:visits'
    assert choose_source(profile, result).source_id == 'igdb:visits'


def test_no_candidate_advances_source_not_game_cursor():
    state = {**READY, 'last_completed_source_id': 'godotengine/godot-builds',
             'igdb_last_game_id': 87622}
    result = next_state(
        {'status': 'SKIP_NO_CANDIDATE'}, NOW, state, writer=False,
        no_candidate=True, source_id='igdb:visits',
    )
    assert result['last_completed_source_id'] == 'igdb:visits'
    assert result['igdb_last_game_id'] == 87622
    assert result['not_before'] == NOW + INTERVAL
    # A caller cannot advance the cursor by naming an unconfirmed outcome.
    unconfirmed = next_state(
        {'status': 'SKIP_NO_CANDIDATE'}, NOW, state,
        source_id='igdb:visits',
    )
    assert unconfirmed['last_completed_source_id'] == 'godotengine/godot-builds'


def test_game_cursor_state_schema_is_strict(tmp_path):
    valid = {**READY, 'igdb_last_game_id': 87622}
    assert load_state(tmp_path, lambda _: valid) == valid
    for invalid in (True, 0, -1, None, '87622', 10**20):
        with pytest.raises(RuntimeError, match='SCHEDULER_STATE_INVALID'):
            load_state(tmp_path, lambda _: {
                **READY, 'igdb_last_game_id': invalid,
            })


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_igdb_cursor_round_trip_and_no_candidate_without_writer(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('igdb:visits', 'godotengine/godot-builds')
    initial = {**READY, 'last_completed_source_id': 'godotengine/godot-builds',
               'igdb_last_game_id': 87622}
    calls = []

    def child(uid, role, envelope=None, *, source_id=None,
              after_game_id=None):
        calls.append((role, source_id, after_game_id))
        if role == 'collect':
            assert source_id == 'igdb:visits'
            assert after_game_id == 87622
            return 0, {'source_id': source_id,
                       'status': 'NO_ELIGIBLE_CANDIDATE'}
        raise AssertionError('Writer must not run for an empty candidate list')

    assert cycle(profile, path, initial, child=child,
                 clock=lambda: NOW) == {'status': 'SKIP_NO_CANDIDATE'}
    final = json.loads(path.read_text())
    assert final['pending'] is False
    assert final['not_before'] == NOW + INTERVAL
    assert final['igdb_last_game_id'] == 87622
    assert final['last_completed_source_id'] == 'igdb:visits'
    assert choose_source(profile, final).source_id == 'godotengine/godot-builds'
    assert calls == [('collect', 'igdb:visits', 87622)]


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_confirmed_igdb_game_id_updates_cursor_and_survives_restart(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('igdb:visits')
    calls = []

    def child(uid, role, envelope=None, *, source_id=None,
              after_game_id=None):
        if role == 'collect':
            calls.append(after_game_id)
            assert source_id == 'igdb:visits'
            game_id = 115 if after_game_id == 87622 else 87622
            return 0, {'source_id': source_id, 'preview': {
                'candidate_identity': f'igdb-game:{game_id}',
            }}
        return 0, {'status': 'SKIP_EXISTING_RELEASE',
                   'candidate_identity': envelope['preview']['candidate_identity']}

    assert cycle(profile, path, READY, child=child,
                 clock=lambda: NOW)['status'] == 'SKIP_EXISTING_RELEASE'
    loaded = load_state(path, lambda name: json.loads(name.read_text()))
    assert loaded['igdb_last_game_id'] == 87622
    assert cycle(profile, path, loaded, child=child,
                 clock=lambda: NOW + INTERVAL)['status'] == (
                     'SKIP_EXISTING_RELEASE'
                 )
    assert json.loads(path.read_text())['igdb_last_game_id'] == 115
    assert calls == [None, 87622]


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
@pytest.mark.parametrize('writer_response', [
    {'status': 'COMMITTED', 'candidate_identity': 'igdb-game:999'},
    {'status': 'SKIP_EXISTING_RELEASE'},
    {'status': 'COMMITTED', 'candidate_identity': True},
])
def test_wrong_igdb_writer_identity_keeps_pending(tmp_path, writer_response):
    path = tmp_path / 'state.json'
    profile = _profile('igdb:visits')
    child = Mock(side_effect=[
        (0, {'source_id': 'igdb:visits',
             'preview': {'candidate_identity': 'igdb-game:87622'}}),
        (0, writer_response),
    ])
    with pytest.raises(RuntimeError, match='GAME_CURSOR_UNCONFIRMED'):
        cycle(profile, path, READY, child=child, clock=lambda: NOW)
    assert json.loads(path.read_text())['pending'] is True


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
def test_fake_no_candidate_for_godot_never_advances(tmp_path):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits')
    child = Mock(return_value=(0, {
        'source_id': 'godotengine/godot-builds',
        'status': 'NO_ELIGIBLE_CANDIDATE',
    }))
    with pytest.raises(RuntimeError, match='COLLECTOR_SOURCE_MISMATCH'):
        cycle(profile, path, READY, child=child, clock=lambda: NOW)
    assert json.loads(path.read_text())['pending'] is True


@pytest.mark.skipif(os.name != 'posix', reason='Linux child process contract')
def test_child_accepts_igdb_empty_only_and_passes_cursor(monkeypatch):
    import pwd

    from scripts import auto_supply_control as control

    monkeypatch.setattr(pwd, 'getpwuid', lambda _: SimpleNamespace(
        pw_name='trend-collector', pw_gid=200,
    ))
    runner = Mock(return_value=SimpleNamespace(
        returncode=0,
        stdout=b'{"source_id":"igdb:visits","status":"NO_ELIGIBLE_CANDIDATE"}',
    ))
    monkeypatch.setattr(control.subprocess, 'run', runner)
    code, result = control.run_child(101, 'collect', source_id='igdb:visits',
                                     after_game_id=87622)
    assert code == 0 and result['status'] == 'NO_ELIGIBLE_CANDIDATE'
    assert runner.call_args.args[0][-4:] == [
        '--source-id', 'igdb:visits', '--after-game-id', '87622',
    ]
    with pytest.raises(RuntimeError, match='GAME_CURSOR_INVALID'):
        control.run_child(101, 'collect', source_id='igdb:visits',
                          after_game_id=True)
    with pytest.raises(RuntimeError, match='GAME_CURSOR_INVALID'):
        control.run_child(101, 'collect', source_id='godotengine/godot-builds',
                          after_game_id=87622)
    with pytest.raises(RuntimeError, match='CHILD_OUTCOME_UNKNOWN'):
        control.run_child(101, 'collect', source_id='godotengine/godot-builds')


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
@pytest.mark.parametrize('source', [
    'searchapi-kr-reviewed-news', 'searchapi-kr-interest',
])
def test_searchapi_empty_rotates_without_writer_or_cursor_change(tmp_path, source):
    path = tmp_path / 'state.json'
    profile = _profile('godotengine/godot-builds', 'igdb:visits', source)
    initial = {**READY, 'last_completed_source_id': 'igdb:visits',
               'igdb_last_game_id': 87622}
    child = Mock(return_value=(0, {
        'source_id': source, 'status': 'NO_ELIGIBLE_CANDIDATE',
    }))
    assert cycle(profile, path, initial, child=child,
                 clock=lambda: NOW) == {'status': 'SKIP_NO_CANDIDATE'}
    child.assert_called_once_with(101, 'collect', source_id=source)
    final = json.loads(path.read_text())
    assert final == {**READY, 'not_before': NOW + INTERVAL,
                     'last_completed_source_id': source,
                     'igdb_last_game_id': 87622}
    assert choose_source(profile, final).source_id == 'godotengine/godot-builds'


@pytest.mark.skipif(os.name != 'posix', reason='Linux durable state only')
@pytest.mark.parametrize('matches', [True, False])
@pytest.mark.parametrize(('source', 'prefix', 'reason'), [
    ('searchapi-kr-reviewed-news', 'searchapi-event:',
     'NEWS_WRITER_IDENTITY_UNCONFIRMED'),
    ('searchapi-kr-interest', 'searchapi-interest:',
     'INTEREST_WRITER_IDENTITY_UNCONFIRMED'),
])
def test_searchapi_writer_identity_controls_rotation(
    tmp_path, matches, source, prefix, reason,
):
    path = tmp_path / 'state.json'
    key = 'a' * 64
    profile = _profile(source, 'igdb:visits')
    envelope = {'source_id': source, 'preview': {'case_key': key}}
    result = {'status': 'COMMITTED',
              'candidate_identity': prefix + (key if matches else 'b' * 64)}
    child = Mock(side_effect=[(0, envelope), (0, result)])
    if matches:
        assert cycle(profile, path, READY, child=child,
                     clock=lambda: NOW) == result
        state = json.loads(path.read_text())
        assert state['last_completed_source_id'] == source
        assert not state['pending']
        assert choose_source(profile, state).source_id == 'igdb:visits'
    else:
        with pytest.raises(RuntimeError, match=reason):
            cycle(profile, path, READY, child=child, clock=lambda: NOW)
        assert json.loads(path.read_text())['pending']


@pytest.mark.skipif(os.name != 'posix', reason='Linux child process contract')
@pytest.mark.parametrize('source', [
    'searchapi-kr-reviewed-news', 'searchapi-kr-interest',
])
def test_child_accepts_searchapi_empty_but_not_wrong_source(monkeypatch, source):
    import pwd

    from scripts import auto_supply_control as control
    monkeypatch.setattr(pwd, 'getpwuid', lambda _: SimpleNamespace(
        pw_name='trend-collector', pw_gid=200,
    ))
    runner = Mock(return_value=SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            'source_id': source, 'status': 'NO_ELIGIBLE_CANDIDATE',
        }).encode(),
    ))
    monkeypatch.setattr(control.subprocess, 'run', runner)
    assert control.run_child(101, 'collect', source_id=source)[0] == 0
    with pytest.raises(RuntimeError, match='CHILD_OUTCOME_UNKNOWN'):
        control.run_child(101, 'collect', source_id='igdb:visits')
