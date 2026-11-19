"""Isolated SYN-01/02/05 policy. Injected I/O; importing never accesses Windows."""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re

ROOT = r"C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01"
ADMIN, SYSTEM = "S-1-5-32-544", "S-1-5-18"
F_READ, F_WRITE, D_READ = 0x120089, 0x120116, 0x1200A9
DELETE, READ_CONTROL, WRITE_DAC, WRITE_OWNER = 0x10000, 0x20000, 0x40000, 0x80000
F_RW, F_RW_DELETE = F_READ | F_WRITE, F_READ | F_WRITE | DELETE
GATE = r"Store\locks\global.gate"
FRAGMENT = b"SYNTHETIC_PHASE4B2_PARTIAL_ONLY\n"
CONTENT = b"SYNTHETIC_PHASE4B2_IO_ONLY\n"
DIRS = {"": D_READ, "Config": D_READ, "Control": D_READ, "Store": D_READ,
        r"Store\work": D_READ | 6, r"Store\locks": D_READ | 2,
        "Evidence": D_READ | 2}
CONFIG = (r"Config\settings.synthetic.json", r"Config\reviewers.synthetic.json")
INVENTORY = r"Control\inventory.private.json"
WORK_DIRS = (r"Store\work\SYN02", r"Store\work\SYN05-crash")
IO, RENAMED = WORK_DIRS[0] + r"\io.bin", WORK_DIRS[0] + r"\io-renamed.bin"
PARTIAL = WORK_DIRS[1] + r"\partial.bin"
EVIDENCE = {case: rf"Evidence\{case.lower().replace('-', '')}.public.json"
            for case in ("SYN-01", "SYN-02", "SYN-05")}
PRIVATE = r"Evidence\native.private.json"
NAMES = set(DIRS) | set(CONFIG) | {INVENTORY, GATE, IO, RENAMED, PARTIAL, PRIVATE}
NAMES |= set(WORK_DIRS) | set(EVIDENCE.values())
CODES = set("""PATH_NOT_APPROVED EXECUTION_NOT_APPROVED ADMIN_TOKEN_REQUIRED
NORMAL_TOKEN_REQUIRED ROOT_COLLISION NATIVE_FAILURE GATE_COLLISION
OBJECT_MISMATCH ACL_MISMATCH UNEXPECTED_OBJECT CONFIG_CHANGED INVALID_INVENTORY
UNEXPECTED_ACCESS WRONG_DENIAL STAGE_COLLISION PREREQUISITE_MISSING
IDENTITY_MISMATCH IPC_FAILURE CHILD_FAILURE TIMEOUT EXPECTED_CRASH_RESIDUE
PLAN_ONLY PREFLIGHT_ONLY OBSERVED INTERNAL_ERROR INVALID_ARGUMENTS UNSUPPORTED
""".split())
PREFLIGHT_KEYS = ("token_elevated", "token_dangerous_privileges", "known_folder_matches",
                  "ancestors_checked", "root_exists", "native_read_checks_completed")


class Hold(Exception):
    def __init__(self, code):
        self.code = code if code in CODES else "INTERNAL_ERROR"
        super().__init__(self.code)


class NativeFailure(Exception):
    def __init__(self, winerror):
        self.winerror = int(winerror)
        super().__init__("NATIVE_FAILURE")  # Never retain WinError(path/message).


@dataclass(frozen=True)
class Token:
    sid: str = field(repr=False)
    elevated: bool
    dangerous_privileges: bool


@dataclass(frozen=True, repr=False)
class Info:
    identity: tuple
    owner: str
    aces: tuple
    directory: bool
    reparse: bool
    links: int
    protected: bool = True


def aces(sid, mask):
    return tuple(sorted(((ADMIN, 0x1F01FF, 0, 0), (SYSTEM, 0x1F01FF, 0, 0),
                         (sid, mask, 0, 0))))


def verify(info, sid, owner, mask, directory):
    if info.reparse or info.directory != directory or (not directory and info.links != 1):
        raise Hold("OBJECT_MISMATCH")
    if not info.protected or info.owner != owner or info.aces != aces(sid, mask):
        raise Hold("ACL_MISMATCH")
    return info


def result(status, code, case="PLAN", winerror=None, *, preflight=None):
    out = {"status": status if status in ("HOLD", "BLOCKED", "PLAN_ONLY",
                                           "PREFLIGHT_ONLY", "SYNTHETIC_OBSERVED") else "HOLD",
            "code": code if code in CODES else "INTERNAL_ERROR",
            "case": case if case in ("PLAN", "PREFLIGHT", "SYN-01", "SYN-02", "SYN-05") else "PLAN",
            "operational_approval": "NONE",
            "win32_error_code": winerror if type(winerror) is int and 0 <= winerror <= 0xFFFFFFFF else None}
    if out["case"] == "PREFLIGHT" and isinstance(preflight, dict) and set(preflight) == set(PREFLIGHT_KEYS):
        out["preflight"] = {key: preflight[key] if type(preflight[key]) is bool else None
                            for key in PREFLIGHT_KEYS}
    return out


def print_result(value):
    # Reconstruct fixed fields. Never serialize arbitrary exception/adapter data.
    print(json.dumps(result(value["status"], value["code"], value["case"],
                            value.get("win32_error_code"), preflight=value.get("preflight"))))


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def decode(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise Hold("INVALID_INVENTORY")
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as error:
        raise Hold("INVALID_INVENTORY") from error


@contextmanager
def opened(native, name, access=READ_CONTROL | 0x80, directory=False, share=1):
    handle = native.open(name, access, directory, share)
    try:
        yield handle
    finally:
        native.close(handle)


def assert_denied(native, name, access, directory):
    try:
        handle = native.open(name, access, directory, 3)
    except NativeFailure as error:
        if error.winerror == 5:
            return
        raise Hold("WRONG_DENIAL") from error
    else:
        native.close(handle)
        raise Hold("UNEXPECTED_ACCESS")


class Gate:
    def __init__(self, native, handle, info, sid):
        self.native, self.handle, self.initial, self.sid = native, handle, info, sid
        self.active = True

    @classmethod
    def acquire(cls, native, sid):
        try:
            handle = native.create_file(GATE, sid, F_RW_DELETE, gate=True)
        except NativeFailure as error:
            raise Hold("GATE_COLLISION" if error.winerror in (80, 183, 32)
                       else "NATIVE_FAILURE") from error
        try:
            info = verify(native.info(handle), sid, sid, F_RW_DELETE, False)
        except BaseException:
            native.close(handle)  # Leave the newly created file, never repair.
            raise
        return cls(native, handle, info, sid)

    def check(self):
        if not self.active:
            raise Hold("IDENTITY_MISMATCH")
        current = verify(self.native.info(self.handle), self.sid, self.sid, F_RW_DELETE, False)
        if current != self.initial:
            raise Hold("IDENTITY_MISMATCH")

    def release(self):
        try:
            self.check()
            self.native.mark_delete(self.handle)
        finally:
            self.abandon()

    def abandon(self):
        if self.active:
            self.active = False
            self.native.close(self.handle)


class Lab:
    def __init__(self, native, *, root=ROOT):
        if not isinstance(root, str) or root.casefold() != ROOT.casefold():
            raise Hold("PATH_NOT_APPROVED")
        self.native = native

    def _token(self, elevated):
        token = self.native.token()
        if not re.fullmatch(r"S-1-(?:\d+-)+\d+", token.sid):
            raise Hold("IDENTITY_MISMATCH")
        if token.elevated is not elevated or (not elevated and token.dangerous_privileges):
            raise Hold("ADMIN_TOKEN_REQUIRED" if elevated else "NORMAL_TOKEN_REQUIRED")
        return token

    @staticmethod
    def _approved(approved):
        if approved is not True:
            raise Hold("EXECUTION_NOT_APPROVED")

    def preflight(self):
        facts = dict.fromkeys(PREFLIGHT_KEYS)
        facts["native_read_checks_completed"] = False
        try:
            token = self.native.token()  # TOKEN_QUERY only, no privilege changes.
            if (not isinstance(token.sid, str) or not re.fullmatch(r"S-1-(?:\d+-)+\d+", token.sid)
                    or type(token.elevated) is not bool or type(token.dangerous_privileges) is not bool):
                raise Hold("IDENTITY_MISMATCH")
            facts["token_elevated"] = token.elevated
            facts["token_dangerous_privileges"] = token.dangerous_privileges
            with self.native.parents():
                facts["known_folder_matches"] = True
                facts["ancestors_checked"] = True
                facts["root_exists"] = self.native.exists("")
                if type(facts["root_exists"]) is not bool:
                    raise Hold("OBJECT_MISMATCH")
                if facts["root_exists"]:
                    raise Hold("ROOT_COLLISION")
            facts["native_read_checks_completed"] = True
        except NativeFailure as error:
            return result("HOLD", "NATIVE_FAILURE", "PREFLIGHT", error.winerror, preflight=facts)
        except Hold as error:
            return result("HOLD", error.code, "PREFLIGHT", preflight=facts)
        return result("PREFLIGHT_ONLY", "PREFLIGHT_ONLY", "PREFLIGHT", preflight=facts)

    def _new_file(self, name, sid, owner, mask, payload):
        handle = self.native.create_file(name, owner, mask)
        try:
            info = verify(self.native.info(handle), sid, owner, mask, False)
            self.native.write(handle, payload)
            self.native.flush(handle)
            if self.native.read(handle) != payload or self.native.info(handle) != info:
                raise Hold("OBJECT_MISMATCH")
            return info
        finally:
            self.native.close(handle)

    def _tree(self, allowed=NAMES):
        for directory in (*DIRS, *WORK_DIRS):
            if self.native.exists(directory):
                expected = {p.rsplit("\\", 1)[-1] for p in allowed if p and
                            (p.rsplit("\\", 1)[0] if "\\" in p else "") == directory}
                if not set(self.native.children(directory)) <= expected:
                    raise Hold("UNEXPECTED_OBJECT")

    def initialize(self, *, approved=False):
        self._approved(approved)
        token = self._token(True)
        sid = token.sid
        with self.native.parents(), ExitStack() as stack:
            if self.native.exists(""):
                raise Hold("ROOT_COLLISION")
            pinned, objects = [], {}
            for name, mask in DIRS.items():
                self.native.create_dir(name, ADMIN, mask)
                h = stack.enter_context(opened(self.native, name, directory=True, share=3))
                info = verify(self.native.info(h), sid, ADMIN, mask, True)
                objects[name] = list(info.identity)
                pinned.append((h, info))
            for name, payload in zip(CONFIG, (
                    encode({"schema": "SYNTHETIC_ONLY", "store": "LAB_ONLY"}),
                    encode({"schema": "SYNTHETIC_ONLY", "reviewer_sid": sid}))):
                objects[name] = list(self._new_file(name, sid, ADMIN, F_READ, payload).identity)
            hashes = {}
            for name in CONFIG:
                with opened(self.native, name, F_READ) as h:
                    verify(self.native.info(h), sid, ADMIN, F_READ, False)
                    hashes[name] = sha256(self.native.read(h)).hexdigest()
            inventory = {"schema": "ACL_LAB_R01", "sid": sid, "objects": objects,
                         "config_hashes": hashes}
            self._new_file(INVENTORY, sid, ADMIN, F_READ, encode(inventory))
            # Private content is written only after initial owner/ACL validation.
            for h, info in pinned:
                if self.native.info(h) != info:
                    raise Hold("OBJECT_MISMATCH")
            self._tree(set(DIRS) | set(CONFIG) | {INVENTORY, EVIDENCE["SYN-01"]})
            out = result("SYNTHETIC_OBSERVED", "OBSERVED", "SYN-01")
            self._new_file(EVIDENCE["SYN-01"], sid, sid, F_RW, encode(out))
            return out

    @contextmanager
    def session(self):
        token = self._token(False)
        sid = token.sid
        with self.native.parents(), ExitStack() as stack:
            pinned = []
            for name, mask in DIRS.items():
                h = stack.enter_context(opened(self.native, name, directory=True, share=3))
                pinned.append((h, verify(self.native.info(h), sid, ADMIN, mask, True)))
            inv = stack.enter_context(opened(self.native, INVENTORY, F_READ))
            pinned.append((inv, verify(self.native.info(inv), sid, ADMIN, F_READ, False)))
            raw = self.native.read(inv)
            data = decode(raw)
            if (not isinstance(data, dict) or set(data) != {"schema", "sid", "objects", "config_hashes"}
                    or data["schema"] != "ACL_LAB_R01" or data["sid"] != sid
                    or not isinstance(data["objects"], dict)
                    or set(data["objects"]) != set(DIRS) | set(CONFIG)
                    or not isinstance(data["config_hashes"], dict)
                    or set(data["config_hashes"]) != set(CONFIG)):
                raise Hold("INVALID_INVENTORY")
            for identity in data["objects"].values():
                if (not isinstance(identity, list) or len(identity) != 2
                        or type(identity[0]) is not int or identity[0] < 0
                        or not isinstance(identity[1], str)
                        or not re.fullmatch("[0-9a-f]{32}", identity[1])):
                    raise Hold("INVALID_INVENTORY")
            if any(not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)
                   for digest in data["config_hashes"].values()):
                raise Hold("INVALID_INVENTORY")
            for (name, _mask), (_h, info) in zip(DIRS.items(), pinned):
                if list(info.identity) != data["objects"][name]:
                    raise Hold("IDENTITY_MISMATCH")
            config_handles = []
            for name in CONFIG:
                h = stack.enter_context(opened(self.native, name, F_READ))
                info = verify(self.native.info(h), sid, ADMIN, F_READ, False)
                pinned.append((h, info))
                if list(info.identity) != data["objects"][name]:
                    raise Hold("IDENTITY_MISMATCH")
                config_handles.append((h, data["config_hashes"][name]))
            completed = stack.enter_context(opened(self.native, EVIDENCE["SYN-01"], F_READ))
            pinned.append((completed, verify(self.native.info(completed), sid, sid, F_RW, False)))
            expected = encode(result("SYNTHETIC_OBSERVED", "OBSERVED", "SYN-01"))
            if self.native.read(completed) != expected:
                raise Hold("PREREQUISITE_MISSING")
            config_handles.append((completed, sha256(expected).hexdigest()))

            def checkpoint():
                if self._token(False) != token:
                    raise Hold("IDENTITY_MISMATCH")
                if any(self.native.info(h) != info for h, info in pinned):
                    raise Hold("OBJECT_MISMATCH")
                if self.native.read(inv) != raw or any(
                        sha256(self.native.read(h)).hexdigest() != digest
                        for h, digest in config_handles):
                    raise Hold("CONFIG_CHANGED")
                self._tree()
            checkpoint()
            yield sid, checkpoint
            checkpoint()

    def io_trial(self, *, approved=False):
        self._approved(approved)
        with self.session() as (sid, check):
            if any(self.native.exists(p) for p in (WORK_DIRS[0], EVIDENCE["SYN-02"])):
                raise Hold("STAGE_COLLISION")
            gate = Gate.acquire(self.native, sid)
            try:
                check()
                # Same APIs/flags as positive reads; each forbidden mask tested separately.
                for name in ("Config", *CONFIG):
                    directory = name == "Config"
                    with opened(self.native, name, D_READ if directory else F_READ,
                                directory, 3):
                        pass
                    for mask in ((2, 4, 0x40, DELETE, WRITE_DAC, WRITE_OWNER, 0x100, 0x10)
                                 if directory else
                                 (2, 4, DELETE, WRITE_DAC, WRITE_OWNER, 0x100, 0x10)):
                        assert_denied(self.native, name, mask, directory)
                check()
                self.native.create_dir(WORK_DIRS[0], sid, D_READ | 6 | DELETE)
                with opened(self.native, WORK_DIRS[0], directory=True, share=3) as d:
                    verify(self.native.info(d), sid, sid, D_READ | 6 | DELETE, True)
                    h = self.native.create_file(IO, sid, F_RW_DELETE)
                    try:
                        info = verify(self.native.info(h), sid, sid, F_RW_DELETE, False)
                        check()
                        self.native.write(h, CONTENT)
                        self.native.flush(h)
                        if self.native.read(h) != CONTENT:
                            raise Hold("OBJECT_MISMATCH")
                        check()
                        self.native.rename(h, RENAMED)
                        if self.native.info(h) != info or self.native.read(h) != CONTENT:
                            raise Hold("OBJECT_MISMATCH")
                    finally:
                        self.native.close(h)
                check()
                out = result("SYNTHETIC_OBSERVED", "OBSERVED", "SYN-02")
                self._new_file(EVIDENCE["SYN-02"], sid, sid, F_RW, encode(out))
                check()
                gate.release()
            finally:
                gate.abandon()
            return out

    def concurrent_trial(self, driver, *, approved=False):
        self._approved(approved)
        with self.session() as (sid, check), driver:
            if any(self.native.exists(p) for p in
                   (WORK_DIRS[1], EVIDENCE["SYN-05"], PRIVATE)):
                raise Hold("STAGE_COLLISION")
            if self.native.exists(GATE):
                raise Hold("GATE_COLLISION")
            for name, mask, payload in (
                    (EVIDENCE["SYN-02"], F_RW, encode(result("SYNTHETIC_OBSERVED", "OBSERVED", "SYN-02"))),
                    (RENAMED, F_RW_DELETE, CONTENT)):
                if not self.native.exists(name):
                    raise Hold("PREREQUISITE_MISSING")
                with opened(self.native, name, F_READ) as h:
                    verify(self.native.info(h), sid, sid, mask, False)
                    if self.native.read(h) != payload:
                        raise Hold("PREREQUISITE_MISSING")
            first = driver.spawn("hold", alternate_cwd=False)
            driver.expect(first, "GATE_HELD")
            contender = driver.spawn("contend", alternate_cwd=True)
            driver.expect(contender, "GATE_COLLISION")
            driver.finish(contender, 1)
            check()
            driver.release(first)
            successor = driver.spawn("hold", alternate_cwd=True)
            driver.expect(successor, "GATE_HELD")
            driver.release(successor)
            check()
            crash = driver.spawn("crash", alternate_cwd=False)
            phase = driver.expect(crash, "PARTIAL_READY")
            check()
            driver.stop_identified(crash)
            for name, key, mask in ((GATE, "gate", F_RW_DELETE), (PARTIAL, "partial", F_RW)):
                with opened(self.native, name, F_READ) as h:
                    info = verify(self.native.info(h), sid, sid, mask, False)
                    if list(info.identity) != phase[key]:
                        raise Hold("IDENTITY_MISMATCH")
                    if name == PARTIAL and self.native.read(h) != FRAGMENT:
                        raise Hold("OBJECT_MISMATCH")
            blocked = driver.spawn("contend", alternate_cwd=True)
            blocked_phase = driver.expect(blocked, "GATE_COLLISION")
            driver.finish(blocked, 1)
            check()
            # Diagnostic evidence only. The stale Gate/partial are NEVER removed.
            self._new_file(PRIVATE, sid, sid, F_RW, encode(driver.private_evidence()))
            out = result("HOLD", "EXPECTED_CRASH_RESIDUE", "SYN-05", blocked_phase.get("win32_error_code"))
            self._new_file(EVIDENCE["SYN-05"], sid, sid, F_RW, encode(out))
            return out


def worker(native, mode, receive, send, *, approved=False):
    """Private IPC worker, called only by the explicit harness execution mode."""
    Lab._approved(approved)
    if mode not in ("hold", "contend", "crash"):
        raise Hold("IPC_FAILURE")
    with Lab(native).session() as (sid, check):
        gate = None
        try:
            try:
                gate = Gate.acquire(native, sid)
            except Hold as error:
                if error.code == "GATE_COLLISION":
                    send("GATE_COLLISION", win32_error_code=error.__cause__.winerror)
                    return 1
                raise
            check()
            if mode == "contend":
                raise Hold("UNEXPECTED_ACCESS")
            if mode == "hold":
                send("GATE_HELD", gate=list(gate.initial.identity))
                if receive() != "release":
                    raise Hold("IPC_FAILURE")
                check()
                gate.release()
                send("RELEASED")
                return 0
            if mode != "crash" or native.exists(WORK_DIRS[1]):
                raise Hold("STAGE_COLLISION")
            native.create_dir(WORK_DIRS[1], sid, D_READ | 6 | DELETE)
            with opened(native, WORK_DIRS[1], directory=True, share=3) as d:
                verify(native.info(d), sid, sid, D_READ | 6 | DELETE, True)
                info = Lab(native)._new_file(PARTIAL, sid, sid, F_RW, FRAGMENT)
                check()
                gate.check()
                send("PARTIAL_READY", gate=list(gate.initial.identity), partial=list(info.identity))
                # No deletion disposition has been set. Parent kills ONLY here.
                receive()
                raise Hold("IPC_FAILURE")
        finally:
            if gate is not None:
                gate.abandon()
