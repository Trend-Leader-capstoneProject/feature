"""Independent local administrator: revoke or launch one approved supply cycle."""

import argparse
import json
import os
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


def next_state(result, now, previous, *, writer=False):
    """Ordinary cycle >=6h apart; rate limit delays are never shortened."""
    status = result.get('status')
    reason = result.get('reason')
    if status == 'HOLD' and reason == 'RATE_LIMITED':
        failures = previous['rate_failures'] + 1
        deadline = result.get('retry_not_before')
        if type(deadline) is not int or deadline < 0 or failures >= 3:
            return {'pending': True, 'not_before': max(now + INTERVAL,
                                      deadline if type(deadline) is int else 0),
                    'rate_failures': failures}
        return {'pending': False,
                'not_before': max(deadline, now + INTERVAL * 2 ** (failures - 1)),
                'rate_failures': failures}
    if writer and status not in {'COMMITTED', 'SKIP_EXISTING_RELEASE'}:
        # Unknown writer outcomes require investigation, not automatic retries.
        return {'pending': True, 'not_before': now + INTERVAL, 'rate_failures': 0}
    return {'pending': False, 'not_before': now + INTERVAL,
            'rate_failures': previous['rate_failures'] if status == 'HOLD' else 0}


def load_state(path, read_record):
    data = read_record(path)
    if (type(data) is not dict or set(data) != {
        'pending', 'not_before', 'rate_failures',
    } or type(data['pending']) is not bool
            or type(data['not_before']) is not int or data['not_before'] < 0
            or type(data['rate_failures']) is not int
            or not 0 <= data['rate_failures'] <= 3):
        raise RuntimeError('SCHEDULER_STATE_INVALID')
    return data


def run_child(uid, role, envelope=None):
    import pwd

    account = pwd.getpwuid(uid)
    expected = 'trend-collector' if role == 'collect' else 'trend-writer'
    if account.pw_name != expected:
        raise RuntimeError('EXECUTION_PRINCIPAL_MISMATCH')
    result = subprocess.run(
        [str(RUNTIME / 'venv/bin/python'), '-E', '-s', '-B', '-m',
         'scripts.run_auto_supply', role],
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
    if result.returncode == 0 and role == 'collect' and set(payload) != {
        'source_id', 'preview',
    }:
        raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    if result.returncode == 0 and role == 'write' and payload.get('status') not in {
        'COMMITTED', 'SKIP_EXISTING_RELEASE',
    }:
        raise RuntimeError('CHILD_OUTCOME_UNKNOWN')
    return result.returncode, payload


def cycle(profile, path, state, *, child=run_child, clock=time.time):
    if state['pending']:
        return {'status': 'HOLD', 'reason': 'SCHEDULER_INVESTIGATION_REQUIRED'}
    now = int(clock())
    if now < state['not_before']:
        return {'status': 'HOLD', 'reason': 'SCHEDULER_COOLDOWN'}
    # Persist the uncertain state BEFORE either child can make a request.
    atomic_json(path, {**state, 'pending': True})
    code, result = child(profile.collector_uid, 'collect')
    writer = code == 0
    if writer:
        _, result = child(profile.writer_uid, 'write', result)
    atomic_json(path, next_state(result, int(clock()), state, writer=writer))
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
            profile.source(None)  # Exactly one approved source in this MVP.

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
        ) if key in result}))
        success = result.get('status') in {'COMMITTED', 'SKIP_EXISTING_RELEASE'}
        return 0 if success else 2
    except Exception:
        print(json.dumps({'status': 'HOLD', 'reason': 'CONTROL_FAILED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
