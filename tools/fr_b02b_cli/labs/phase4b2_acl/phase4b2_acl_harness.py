"""Standalone lab entry point. Default plan mode does not instantiate Win32."""

import argparse
import os
import re
import sys

if __package__:
    from . import phase4b2_acl_lab as lab
else:
    # Direct script/worker execution resolves siblings from the script directory.
    import phase4b2_acl_lab as lab


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's default echoes unknown user-provided values/paths.
        raise lab.Hold("INVALID_ARGUMENTS")


def child_main(mode, *, approved=False):
    lab.Lab._approved(approved)
    if mode not in ("hold", "contend", "crash"):
        raise lab.Hold("IPC_FAILURE")
    if sys.stdin.isatty() or sys.stdout.isatty():
        raise lab.Hold("IPC_FAILURE")
    if __package__:
        from .phase4b2_acl_native import Win32
    else:
        from phase4b2_acl_native import Win32
    native = Win32(allow_changes=True)
    hello = lab.decode(sys.stdin.readline(4097))
    nonce = hello.get("nonce") if isinstance(hello, dict) else None
    if not isinstance(nonce, str) or not re.fullmatch("[0-9a-f]{64}", nonce):
        raise lab.Hold("IPC_FAILURE")
    handle = native.process_handle(os.getpid())
    try:
        created = native.process_created(handle)
    finally:
        native.close(handle)

    def send(phase, **values):
        print(lab.encode({"nonce": nonce, "created": created, "phase": phase,
                          **values}).decode(), end="", flush=True)

    def receive():
        command = lab.decode(sys.stdin.readline(4097))
        if not isinstance(command, dict) or command.get("nonce") != nonce:
            raise lab.Hold("IPC_FAILURE")
        return command.get("action")

    send("HELLO")
    if receive() != "start":
        raise lab.Hold("IPC_FAILURE")
    return lab.worker(native, mode, receive, send, approved=True)


def main(argv=None, *, native_factory=None, process_factory=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    case = "PLAN"
    try:
        if argv and argv[0] == "_worker":
            if len(argv) != 3 or argv[1] not in ("hold", "contend", "crash") or argv[2] != "--execute-approved-lab":
                raise lab.Hold("EXECUTION_NOT_APPROVED")
            return child_main(argv[1], approved=True)
        parser = Parser(description="Synthetic ACL lab; no operational registration.")
        parser.add_argument("mode", nargs="?", default="plan",
                            choices=("plan", "preflight", "syn01", "syn02", "syn05"))
        parser.add_argument("--execute-approved-lab", action="store_true")
        args = parser.parse_args(argv)
        if args.mode == "plan":
            lab.print_result(lab.result("PLAN_ONLY", "PLAN_ONLY"))
            return 0
        case = {"syn01": "SYN-01", "syn02": "SYN-02", "syn05": "SYN-05"}.get(args.mode, "PREFLIGHT")
        changes = args.mode != "preflight"
        if changes and not args.execute_approved_lab:
            raise lab.Hold("EXECUTION_NOT_APPROVED")
        if native_factory is None:
            if __package__:
                from .phase4b2_acl_native import Win32
            else:
                from phase4b2_acl_native import Win32
            native_factory = Win32
        native = native_factory(allow_changes=changes)
        trial = lab.Lab(native)
        if args.mode == "preflight":
            out = trial.preflight()
        elif args.mode == "syn01":
            out = trial.initialize(approved=True)
        elif args.mode == "syn02":
            out = trial.io_trial(approved=True)
        else:
            if process_factory is None:
                if __package__:
                    from .phase4b2_acl_process import Processes
                else:
                    from phase4b2_acl_process import Processes
                process_factory = Processes
            out = trial.concurrent_trial(process_factory(native, approved=True), approved=True)
        lab.print_result(out)
        return int(out["status"] == "HOLD")
    except lab.Hold as error:
        code = error.__cause__.winerror if isinstance(error.__cause__, lab.NativeFailure) else None
        lab.print_result(lab.result("HOLD", error.code, case, code))
    except lab.NativeFailure as error:
        lab.print_result(lab.result("HOLD", "NATIVE_FAILURE", case, error.winerror))
    except (KeyboardInterrupt, EOFError):
        lab.print_result(lab.result("HOLD", "IPC_FAILURE", case))
    except Exception:
        # Only executable boundary suppresses raw exception/traceback/path/SID.
        lab.print_result(lab.result("HOLD", "INTERNAL_ERROR", case))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
