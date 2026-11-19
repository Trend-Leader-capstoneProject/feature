"""Private bounded IPC and owned-child lifecycle. No process starts on import."""

from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty, Full
import secrets
import subprocess
import sys
from threading import Thread

if __package__:
    from . import phase4b2_acl_lab as lab
else:
    import phase4b2_acl_lab as lab


@dataclass(eq=False, repr=False)
class Child:
    proc: object
    handle: object
    created: int
    nonce: str
    pid: int
    messages: object
    phase: str = ""
    authenticated: bool = False
    events: list = field(default_factory=list)
    mode: str = ""


class Processes:
    def __init__(self, native, *, approved=False, popen=subprocess.Popen):
        self.native, self.popen = native, popen
        self.approved = approved is True
        self.children = []
        self.crash_child = None
        self.crash_started = False

    def _execution_intent(self):
        lab.Lab._approved(self.approved)
        if self.native.allow_changes is not True:
            raise lab.Hold("EXECUTION_NOT_APPROVED")

    def __enter__(self):
        self._execution_intent()
        return self

    def __exit__(self, *_):
        failure = None
        for child in self.children:
            try:
                if child.proc.stdin:
                    child.proc.stdin.close()  # EOF => abandon, NEVER delete/auto-kill.
                if child.proc.poll() is not None:
                    child.proc.stdout.close()
            except (OSError, lab.NativeFailure) as error:
                failure = error
            finally:
                try:
                    self.native.close(child.handle)
                except lab.NativeFailure as error:
                    failure = error
        if failure:
            raise lab.Hold("CHILD_FAILURE") from failure

    def spawn(self, mode, *, alternate_cwd):
        self._execution_intent()  # Before Popen, even with a read-only Native adapter.
        if mode not in ("hold", "contend", "crash"):
            raise lab.Hold("IPC_FAILURE")
        if mode == "crash":
            if self.crash_started:
                raise lab.Hold("CHILD_FAILURE")
            self.crash_started = True
        nonce = secrets.token_hex(32)
        directory = Path(__file__).absolute().parent
        proc = self.popen([sys.executable, "-B", str(directory / "phase4b2_acl_harness.py"),
                           "_worker", mode, "--execute-approved-lab"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                          bufsize=1, cwd=lab.ROOT if alternate_cwd else str(directory),
                          creationflags=subprocess.CREATE_NO_WINDOW)
        handle = None
        try:
            handle = self.native.process_handle(proc.pid)
            created = self.native.process_created(handle)
            messages = Queue(maxsize=8)

            def read_lines():
                try:
                    while True:
                        line = proc.stdout.readline(4097)
                        if not line or len(line) > 4096:
                            messages.put_nowait(None)
                            return
                        messages.put_nowait(lab.decode(line))
                except (OSError, UnicodeError, lab.Hold, Full):
                    try:
                        messages.put_nowait(None)
                    except Full:
                        pass
            Thread(target=read_lines, daemon=True).start()
            child = Child(proc, handle, created, nonce, proc.pid, messages, mode=mode)
            self.children.append(child)
            if mode == "crash":
                self.crash_child = child
            proc.stdin.write(lab.encode({"nonce": nonce}).decode())
            proc.stdin.flush()
            self.expect(child, "HELLO")
            child.authenticated = True
            self._send(child, "start")
            return child
        except BaseException:
            if handle is not None and not any(x.handle is handle for x in self.children):
                self.native.close(handle)
            if proc.stdin:
                proc.stdin.close()
            raise

    def expect(self, child, phase):
        if child not in self.children:
            raise lab.Hold("IDENTITY_MISMATCH")
        try:
            data = child.messages.get(timeout=5)
        except Empty as error:
            raise lab.Hold("TIMEOUT") from error
        extra = ({"gate", "partial"} if phase == "PARTIAL_READY" else
                 {"gate"} if phase == "GATE_HELD" else
                 {"win32_error_code"} if phase == "GATE_COLLISION" else set())
        if (not isinstance(data, dict) or data.get("nonce") != child.nonce
                or data.get("created") != child.created or data.get("phase") != phase
                or set(data) != {"nonce", "created", "phase"} | extra):
            raise lab.Hold("IPC_FAILURE")
        for key in extra:
            if key == "win32_error_code":
                if type(data[key]) is not int or data[key] not in (80, 183, 32):
                    raise lab.Hold("IPC_FAILURE")
                continue
            identity = data[key]
            if (not isinstance(identity, list) or len(identity) != 2
                    or type(identity[0]) is not int or identity[0] < 0
                    or not isinstance(identity[1], str) or len(identity[1]) != 32
                    or any(ch not in "0123456789abcdef" for ch in identity[1])):
                raise lab.Hold("IPC_FAILURE")
        child.phase = phase
        child.events.append(data)
        return data

    @staticmethod
    def _send(child, action):
        try:
            child.proc.stdin.write(lab.encode({"action": action, "nonce": child.nonce}).decode())
            child.proc.stdin.flush()
        except OSError as error:
            raise lab.Hold("IPC_FAILURE") from error

    @staticmethod
    def finish(child, code):
        try:
            observed = child.proc.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise lab.Hold("TIMEOUT") from error
        if observed != code:
            raise lab.Hold("CHILD_FAILURE")

    def release(self, child):
        self._execution_intent()
        if child not in self.children or child.mode != "hold" or not child.authenticated or child.phase != "GATE_HELD":
            raise lab.Hold("IDENTITY_MISMATCH")
        self._send(child, "release")
        self.expect(child, "RELEASED")
        self.finish(child, 0)

    def stop_identified(self, child):
        self._execution_intent()
        if (child not in self.children or child is not self.crash_child or child.mode != "crash" or not child.authenticated
                or child.phase != "PARTIAL_READY" or child.proc.pid != child.pid
                or child.proc.poll() is not None
                or self.native.process_created(child.handle) != child.created):
            raise lab.Hold("IDENTITY_MISMATCH")
        # Once requested, never repeat even if termination/wait outcome is uncertain.
        child.phase = "TERMINATION_REQUESTED"
        self.native.terminate(child.handle)
        self.finish(child, 97)
        child.phase = "TERMINATED"

    def private_evidence(self):
        return [{"pid": child.pid, "created": child.created, "events": child.events,
                 "final_phase": child.phase, "mode": child.mode}
                for child in self.children]
