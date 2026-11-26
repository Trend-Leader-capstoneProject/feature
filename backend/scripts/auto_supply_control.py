"""Independent local administrator: revoke or launch one approved supply cycle."""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CONTROL = Path('/etc/trend-leader/auto-supply')
RUNTIME = Path('/opt/trend-leader-auto-supply')
INTERVAL = 6 * 3600
MAX_OUTPUT = 65536
IGDB_SOURCE_ID = 'igdb:visits'
SEARCHAPI_SOURCE_ID = 'searchapi-kr-reviewed-news'
INTEREST_SOURCE_ID = 'searchapi-kr-interest'
INTEREST_RELATED_SCOPE = 'SEARCHAPI_KR_INTEREST_RELATED_V1'
EMPTY_CANDIDATE_SOURCES = frozenset({
    IGDB_SOURCE_ID, SEARCHAPI_SOURCE_ID, INTEREST_SOURCE_ID,
})
IGDB_GAME = re.compile(r'igdb-game:([1-9][0-9]{0,19})\Z')


def atomic_json(path, value, mode=0o600):
    """Replace only a control record, never the shared lock or Journal."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.auto-supply-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), mode)
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _preserve_rotation(updated, previous, *, source_id=None,
                       completed=False, game_id=None):
    """Keep cursor state coupled to the durable scheduler record."""
    for key in ('last_completed_source_id', 'igdb_last_game_id'):
        if key in previous:
            updated[key] = previous[key]
    if source_id is not None and completed:
        updated['last_completed_source_id'] = source_id
    if game_id is not None and completed and source_id == IGDB_SOURCE_ID:
        updated['igdb_last_game_id'] = game_id
    return updated


def next_state(result, now, previous, *, writer=False, source_id=None,
               no_candidate=False, game_id=None):
    """Global >=6h cooldown; rotate only on a confirmed terminal outcome."""
    status = result.get('status')
    reason = result.get('reason')
    writer_done = writer and status in {'COMMITTED', 'SKIP_EXISTING_RELEASE'}
    empty_done = not writer and no_candidate and status == 'SKIP_NO_CANDIDATE'
    completed = writer_done or empty_done
    if writer and result.get('related_news_status') == 'RATE_LIMITED':
        failures = min(3, previous.get('related_news_rate_failures', 0) + 1)
        deadline = result.get('retry_not_before')
        known = type(deadline) is int and deadline >= 0
        updated = {
            'pending': not completed or not known or failures >= 3,
            'not_before': max(
                now + INTERVAL * 2 ** (failures - 1), deadline if known else 0,
            ),
            'rate_failures': 0 if completed else previous['rate_failures'],
            'related_news_rate_failures': failures,
        }
    elif status == 'HOLD' and reason == 'RATE_LIMITED':
        failures = previous['rate_failures'] + 1
        deadline = result.get('retry_not_before')
        if type(deadline) is not int or deadline < 0 or failures >= 3:
            updated = {'pending': True, 'not_before': max(
                now + INTERVAL, deadline if type(deadline) is int else 0,
            ), 'rate_failures': failures}
        else:
            updated = {'pending': False, 'not_before': max(
                deadline, now + INTERVAL * 2 ** (failures - 1),
            ), 'rate_failures': failures}
    elif writer and not completed:
        # Unknown Writer outcomes require investigation, not automatic replay.
        updated = {'pending': True, 'not_before': now + INTERVAL,
                   'rate_failures': 0}
    else:
        updated = {
            'pending': False, 'not_before': now + INTERVAL,
            'rate_failures': previous['rate_failures'] if status == 'HOLD' else 0,
        }
    # A successful unrelated source must not erase the optional News streak.
    if ('related_news_rate_failures' in previous
            and 'related_news_rate_failures' not in updated
            and not (writer_done and result.get('related_news_status')
                     in {'AVAILABLE', 'EMPTY'})):
        updated['related_news_rate_failures'] = previous['related_news_rate_failures']
    return _preserve_rotation(updated, previous, source_id=source_id,
                              completed=completed, game_id=game_id)


def choose_source(profile, state):
    """Rotate only within the protected, already-approved source list."""
    sources = profile.sources
    if not sources:
        raise RuntimeError('SOURCE_NOT_APPROVED')
    ids = tuple(source.source_id for source in sources)
    if len(ids) != len(set(ids)):
        raise RuntimeError('SOURCE_DUPLICATED')
    previous = state.get('last_completed_source_id')
    index = (ids.index(previous) + 1) % len(ids) if previous in ids else 0
    return profile.source(ids[index])


def load_state(path, read_record):
    data = read_record(path)
    if (type(data) is not dict or not {
        'pending', 'not_before', 'rate_failures',
    } <= set(data) or set(data) - {
        'pending', 'not_before', 'rate_failures', 'last_completed_source_id',
        'igdb_last_game_id', 'related_news_rate_failures',
    } or type(data['pending']) is not bool
            or type(data['not_before']) is not int or data['not_before'] < 0
            or type(data['rate_failures']) is not int
            or not 0 <= data['rate_failures'] <= 3
            or ('related_news_rate_failures' in data
                and (type(data['related_news_rate_failures']) is not int
                     or not 1 <= data['related_news_rate_failures'] <= 3))
            or ('last_completed_source_id' in data
                and (not isinstance(data['last_completed_source_id'], str)
                     or re.fullmatch(r'[a-z0-9][a-z0-9_./:-]{0,127}',
                                     data['last_completed_source_id']) is None))
            or ('igdb_last_game_id' in data
                and (type(data['igdb_last_game_id']) is not int
                     or not 1 <= data['igdb_last_game_id'] < 10**20))):
        raise RuntimeError('SCHEDULER_STATE_INVALID')
    return data


def run_child(uid, role, envelope=None, *, source_id=None,
              after_game_id=None):
    import pwd

    account = pwd.getpwuid(uid)
    if role not in {'collect', 'write'}:
        raise RuntimeError('EXECUTION_ROLE_INVALID')
    if source_id is not None and (
        role != 'collect' or not isinstance(source_id, str)
        or re.fullmatch(r'[a-z0-9][a-z0-9_./:-]{0,127}', source_id) is None
    ):
        raise RuntimeError('SOURCE_ID_INVALID')
    if after_game_id is not None and (
        role != 'collect' or source_id != IGDB_SOURCE_ID
        or type(after_game_id) is not int
        or not 1 <= after_game_id < 10**20
    ):
        raise RuntimeError('GAME_CURSOR_INVALID')
    expected = 'trend-collector' if role == 'collect' else 'trend-writer'
    if account.pw_name != expected:
        raise RuntimeError('EXECUTION_PRINCIPAL_MISMATCH')
    command = [str(RUNTIME / 'venv/bin/python'), '-E', '-s', '-B', '-m',
               'scripts.run_auto_supply', role]
    if source_id is not None:
        command.extend(('--source-id', source_id))
    if after_game_id is not None:
        command.extend(('--after-game-id', str(after_game_id)))
    result = subprocess.run(
        command,
        cwd=RUNTIME / 'backend',
        user=uid, group=account.pw_gid, extra_groups=[],
        env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C.UTF-8'},
        input=json.dumps(envelope).encode() if envelope is not None else b'',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
    )
    if len(result.stdout) > MAX_OUTPUT:
        raise RuntimeError('CHILD_OUTPUT_INVALID')
    payload = json.loads(result.stdout)
    if type(payload) is not dict or result.returncode not in {0, 2}:
        raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    if result.returncode == 2 and payload.get('status') != 'HOLD':
        raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    if result.returncode == 0 and role == 'collect':
        preview = (set(payload) == {'source_id', 'preview'}
                   and type(payload['preview']) is dict)
        empty = (set(payload) == {'source_id', 'status'}
                 and source_id in EMPTY_CANDIDATE_SOURCES
                 and payload['status'] == 'NO_ELIGIBLE_CANDIDATE')
        if (not (preview or empty)
                or (source_id is not None and payload['source_id'] != source_id)):
            raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    if result.returncode == 0 and role == 'write' and payload.get('status') not in {
        'COMMITTED', 'SKIP_EXISTING_RELEASE',
    }:
        raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    return result.returncode, payload


def _confirmed_igdb_game(preview, result):
    """Only a matching independently verified Writer result may move cursor."""
    if type(preview) is not dict or type(result) is not dict:
        raise RuntimeError('GAME_CURSOR_UNCONFIRMED')
    identity = preview.get('candidate_identity')
    if identity != result.get('candidate_identity') or type(identity) is not str:
        raise RuntimeError('GAME_CURSOR_UNCONFIRMED')
    match = IGDB_GAME.fullmatch(identity)
    if match is None:
        raise RuntimeError('GAME_CURSOR_UNCONFIRMED')
    return int(match[1])


def cycle(profile, path, state, *, child=run_child, clock=time.time):
    if state['pending']:
        return {'status': 'HOLD', 'reason': 'SCHEDULER_INVESTIGATION_REQUIRED'}
    now = int(clock())
    if now < state['not_before']:
        return {'status': 'HOLD', 'reason': 'SCHEDULER_COOLDOWN'}
    source = choose_source(profile, state)
    # Persist uncertain state BEFORE either child can make a request.
    atomic_json(path, {**state, 'pending': True})
    kwargs = {'source_id': source.source_id}
    if source.source_id == IGDB_SOURCE_ID and 'igdb_last_game_id' in state:
        kwargs['after_game_id'] = state['igdb_last_game_id']
    code, envelope = child(profile.collector_uid, 'collect', **kwargs)
    writer = False
    no_candidate = False
    game_id = None
    if code == 0:
        if (type(envelope) is dict
                and set(envelope) == {'source_id', 'status'}
                and source.source_id in EMPTY_CANDIDATE_SOURCES
                and envelope['source_id'] == source.source_id
                and envelope['status'] == 'NO_ELIGIBLE_CANDIDATE'):
            no_candidate = True
            result = {'status': 'SKIP_NO_CANDIDATE'}
        else:
            if (type(envelope) is not dict
                    or envelope.get('source_id') != source.source_id
                    or set(envelope) != {'source_id', 'preview'}
                    or type(envelope['preview']) is not dict):
                raise RuntimeError('COLLECTOR_SOURCE_MISMATCH')
            writer = True
            write_code, result = child(profile.writer_uid, 'write', envelope)
            if type(result) is not dict:
                raise RuntimeError('WRITER_OUTCOME_MISMATCH')
            success = result.get('status') in {
                'COMMITTED', 'SKIP_EXISTING_RELEASE',
            }
            if (write_code == 0) != success or write_code not in {0, 2}:
                raise RuntimeError('WRITER_OUTCOME_MISMATCH')
            if (success and source.source_id == INTEREST_SOURCE_ID
                    and getattr(source, 'scope', None) == INTEREST_RELATED_SCOPE
                    and 'related_news_status' not in result):
                raise RuntimeError('RELATED_NEWS_OUTCOME_MISMATCH')
            if 'related_news_status' in result:
                if (
                    source.source_id != INTEREST_SOURCE_ID
                    or getattr(source, 'scope', None) != INTEREST_RELATED_SCOPE
                    or result['related_news_status'] not in {
                        'DISABLED', 'AVAILABLE', 'EMPTY', 'UNAVAILABLE', 'RATE_LIMITED',
                    }
                    or ((result['related_news_status'] == 'RATE_LIMITED')
                        != ('retry_not_before' in result))
                ):
                    raise RuntimeError('RELATED_NEWS_OUTCOME_MISMATCH')
            if source.source_id == IGDB_SOURCE_ID and success:
                game_id = _confirmed_igdb_game(envelope['preview'], result)
            if source.source_id == SEARCHAPI_SOURCE_ID and success:
                key = envelope['preview'].get('case_key')
                identity = result.get('candidate_identity')
                if (not isinstance(key, str)
                        or re.fullmatch(r'[a-f0-9]{64}', key) is None
                        or identity != f'searchapi-event:{key}'):
                    raise RuntimeError('NEWS_WRITER_IDENTITY_UNCONFIRMED')
            if source.source_id == INTEREST_SOURCE_ID and success:
                key = envelope['preview'].get('case_key')
                if (not isinstance(key, str)
                        or re.fullmatch(r'[a-f0-9]{64}', key) is None
                        or result.get('candidate_identity')
                        != f'searchapi-interest:{key}'):
                    raise RuntimeError('INTEREST_WRITER_IDENTITY_UNCONFIRMED')
    elif (code == 2 and type(envelope) is dict
          and envelope.get('status') == 'HOLD'):
        result = envelope
    else:
        raise RuntimeError('COLLECTOR_OUTCOME_MISMATCH')
    # Single-source Godot retains its three-field legacy state.
    rotate = (len(profile.sources) > 1
              or 'last_completed_source_id' in state
              or source.source_id == IGDB_SOURCE_ID)
    updated = next_state(
        result, int(clock()), state, writer=writer,
        no_candidate=no_candidate, game_id=game_id,
        source_id=source.source_id if rotate else None,
    )
    atomic_json(path, updated)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'revoke'))
    args = parser.parse_args()
    try:
        if sys.platform != 'linux' or os.geteuid() != 0:
            raise RuntimeError('ADMIN_LINUX_ROOT_REQUIRED')
        import fcntl

        from scripts.run_auto_supply import (
            _bounded,
            _json,
            _read_profile,
            _root_directory,
            _root_file,
        )

        _root_directory(CONTROL)
        _root_directory(RUNTIME / 'backend')

        def read_record(path):
            with _root_file(path) as stream:
                return _json(_bounded(stream))

        with _root_file(CONTROL / 'control.lock') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == 'revoke':
                path = CONTROL / 'approval.json'
                data = read_record(path)
                if type(data) is not dict:
                    raise RuntimeError('APPROVAL_SCHEMA_MISMATCH')
                atomic_json(path, {**data, 'enabled': False}, 0o644)
                print(json.dumps({'status': 'REVOKED'}))
                return 0
            profile = _read_profile()


        scheduler_lock = CONTROL / 'scheduler.lock'
        state_path = CONTROL / 'scheduler-state.json'
        # First invocation may create scheduler state; missing state after the
        # lock has existed is NOT silently recreated.
        try:
            fd = os.open(scheduler_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
            if os.path.lexists(state_path):
                raise RuntimeError('SCHEDULER_STATE_ALREADY_EXISTS')
            atomic_json(state_path, {'pending': False, 'not_before': 0,
                                     'rate_failures': 0})
        with _root_file(scheduler_lock) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not stat.S_ISREG(state_path.lstat().st_mode):
                raise RuntimeError('SCHEDULER_STATE_INVALID')
            result = cycle(profile, state_path, load_state(state_path, read_record))
        # Only bounded diagnostic fields, never previews or raw stderr.
        print(json.dumps({key: result[key] for key in (
            'status', 'reason', 'candidate_identity', 'retry_not_before',
            'related_news_status',
        ) if key in result}))
        success = result.get('status') in {
            'COMMITTED', 'SKIP_EXISTING_RELEASE', 'SKIP_NO_CANDIDATE',
        }
        return 0 if success else 2
    except Exception:
        print(json.dumps({'status': 'HOLD', 'reason': 'CONTROL_FAILED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
