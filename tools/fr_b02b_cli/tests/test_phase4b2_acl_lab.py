"""Harness safety tests: memory doubles only; no Windows mutation/processes."""

import io
import unittest
from contextlib import redirect_stdout, contextmanager
from dataclasses import replace
from queue import Queue
from unittest.mock import Mock, patch

from labs.phase4b2_acl import phase4b2_acl_lab as lab


SID = "S-1-5-21-100-200-300-1001"


class MemoryNative:
    """No filesystem/OS implementation; explicit memory ACL and failure model."""
    def __init__(self):
        self.current = lab.Token(SID, True, False)
        self.objects, self.handles, self.deleted = {}, {}, set()
        self.sequence = 0
        self.partial_write = False
        self.tamper = False

    def token(self):
        return self.current

    @contextmanager
    def parents(self):
        yield

    def exists(self, name):
        return name in self.objects

    def _create(self, name, owner, mask, directory):
        if name in self.objects:
            raise lab.NativeFailure(80)
        self.sequence += 1
        self.objects[name] = [lab.Info((1, f"{self.sequence:032x}"), owner,
                                      lab.aces(SID, mask), directory, False, 1), b""]

    def create_dir(self, name, owner, mask):
        self._create(name, owner, mask, True)

    def create_file(self, name, owner, mask, gate=False):
        self._create(name, owner, mask, False)
        return self.open(name, 0, False, 0)

    def open(self, name, access, directory, share):
        if name not in self.objects:
            raise lab.NativeFailure(2)
        info = self.objects[name][0]
        mask = next(entry[1] for entry in info.aces if entry[0] == SID)
        if not self.current.elevated and access & ~mask:
            raise lab.NativeFailure(5)
        self.sequence += 1
        self.handles[self.sequence] = name
        return self.sequence

    def close(self, handle):
        name = self.handles.pop(handle)
        if handle in self.deleted:
            self.objects.pop(name)

    def info(self, handle):
        return self.objects[self.handles[handle]][0]

    def children(self, directory):
        return [p.rsplit("\\", 1)[-1] for p in self.objects if p and
                (p.rsplit("\\", 1)[0] if "\\" in p else "") == directory]

    def read(self, handle):
        return self.objects[self.handles[handle]][1]

    def write(self, handle, payload):
        name = self.handles[handle]
        self.objects[name][1] = payload[:3] if self.partial_write else payload
        if self.tamper and name == lab.IO:
            self.objects[lab.CONFIG[0]][1] += b"changed"
        if self.partial_write:
            raise lab.Hold("OBJECT_MISMATCH")

    def flush(self, _handle):
        pass

    def rename(self, handle, destination):
        if self.exists(destination):
            raise lab.NativeFailure(80)
        self.objects[destination] = self.objects.pop(self.handles[handle])
        self.handles[handle] = destination

    def mark_delete(self, handle):
        self.deleted.add(handle)


class HarnessFlowTests(unittest.TestCase):
    def ready(self):
        native = MemoryNative()
        lab.Lab(native).initialize(approved=True)
        native.current = lab.Token(SID, False, False)
        return native

    def test_mock_initialization_and_io_preserve_config(self):
        native = self.ready()
        original = {p: native.objects[p][:] for p in lab.CONFIG}
        out = lab.Lab(native).io_trial(approved=True)
        self.assertEqual(out["status"], "SYNTHETIC_OBSERVED")
        self.assertEqual(native.objects[lab.RENAMED][1], lab.CONTENT)
        self.assertFalse(native.exists(lab.GATE))
        self.assertFalse(native.handles)
        self.assertEqual(original, {p: native.objects[p] for p in lab.CONFIG})

    def test_syn02_result_failure_preserves_gate_without_normal_release(self):
        evidence = lab.EVIDENCE["SYN-02"]
        for failure in ("create", "write", "verify"):
            native = self.ready()
            create_file, write, read = native.create_file, native.write, native.read
            native.mark_delete = Mock(wraps=native.mark_delete)

            def create(name, owner, mask, gate=False):
                if name == evidence and failure == "create":
                    raise lab.NativeFailure(112)
                return create_file(name, owner, mask, gate=gate)

            def fail_write(handle, payload):
                if native.handles[handle] == evidence and failure == "write":
                    write(handle, payload[:3])
                    raise lab.NativeFailure(112)
                return write(handle, payload)

            def fail_read(handle):
                if native.handles[handle] == evidence and failure == "verify":
                    return b"incorrect synthetic result"
                return read(handle)

            native.create_file, native.write, native.read = create, fail_write, fail_read
            with self.subTest(failure=failure):
                with self.assertRaises((lab.NativeFailure, lab.Hold)):
                    lab.Lab(native).io_trial(approved=True)
                self.assertTrue(native.exists(lab.GATE))
                native.mark_delete.assert_not_called()
                self.assertEqual(native.exists(evidence), failure != "create")
                self.assertFalse(native.handles)

    def test_syn02_gate_release_failure_cannot_report_success_from_result_file(self):
        from labs.phase4b2_acl import phase4b2_acl_harness as harness
        for failure in ("disposition", "close"):
            native = self.ready()
            close = native.close
            if failure == "disposition":
                native.mark_delete = Mock(side_effect=lab.NativeFailure(5))
            else:
                def fail_close(handle):
                    gate = native.handles[handle] == lab.GATE
                    close(handle)
                    if gate:
                        # Model deletion having occurred before uncertain close failure.
                        raise lab.NativeFailure(6)
                native.close = fail_close
            output = io.StringIO()
            with self.subTest(failure=failure), redirect_stdout(output):
                code = harness.main(["syn02", "--execute-approved-lab"],
                                    native_factory=Mock(return_value=native))
                self.assertEqual(code, 1)
                observed = lab.decode(output.getvalue())
                self.assertEqual(observed["status"], "HOLD")
                self.assertEqual(observed["code"], "NATIVE_FAILURE")
                self.assertEqual(observed["operational_approval"], "NONE")
                self.assertEqual(native.objects[lab.EVIDENCE["SYN-02"]][1],
                                 lab.encode(lab.result("SYNTHETIC_OBSERVED", "OBSERVED", "SYN-02")))
                self.assertEqual(native.exists(lab.GATE), failure == "disposition")
                self.assertFalse(native.handles)

    def test_mock_partial_write_leaves_hold_and_never_releases_gate(self):
        native = self.ready()
        native.partial_write = True
        with self.assertRaises(lab.Hold):
            lab.Lab(native).io_trial(approved=True)
        self.assertTrue(native.exists(lab.GATE))
        self.assertEqual(native.objects[lab.IO][1], lab.CONTENT[:3])
        self.assertFalse(native.exists(lab.EVIDENCE["SYN-02"]))
        self.assertFalse(native.handles)

    def test_mock_config_tamper_blocks_before_rename_and_keeps_hold(self):
        native = self.ready()
        native.tamper = True
        with self.assertRaises(lab.Hold):
            lab.Lab(native).io_trial(approved=True)
        self.assertFalse(native.exists(lab.RENAMED))
        self.assertTrue(native.exists(lab.GATE))
        self.assertFalse(native.handles)

    def test_mock_changed_root_identity_and_unknown_file_block(self):
        for change in ("identity", "unknown", "reparse", "acl"):
            native = self.ready()
            if change == "unknown":
                native._create("foreign", SID, lab.F_RW, False)
            else:
                info = native.objects[""][0]
                native.objects[""][0] = replace(info, **{
                    "identity": {"identity": (2, "b" * 32)},
                    "reparse": {"reparse": True}, "acl": {"protected": False},
                }[change])
            with self.subTest(change=change), self.assertRaises(lab.Hold):
                lab.Lab(native).io_trial(approved=True)
            self.assertFalse(native.exists(lab.GATE))

    def test_mock_missing_initial_completion_is_not_resumed(self):
        native = self.ready()
        native.objects.pop(lab.EVIDENCE["SYN-01"])
        with self.assertRaises(lab.NativeFailure):
            lab.Lab(native).io_trial(approved=True)
        self.assertFalse(native.exists(lab.GATE))

    def test_mock_repeated_stage_does_not_reuse_work(self):
        native = self.ready()
        lab.Lab(native).io_trial(approved=True)
        with self.assertRaises(lab.Hold) as caught:
            lab.Lab(native).io_trial(approved=True)
        self.assertEqual(caught.exception.code, "STAGE_COLLISION")

    def test_mock_non_elevated_token_with_dangerous_privilege_is_blocked(self):
        native = self.ready()
        native.current = lab.Token(SID, False, True)
        with self.assertRaises(lab.Hold):
            lab.Lab(native).io_trial(approved=True)
        self.assertFalse(native.exists(lab.GATE))

    def test_private_inventory_created_after_acl_verified(self):
        native = MemoryNative()
        old_info = native.info

        def wrong_acl(handle):
            info = old_info(handle)
            return replace(info, protected=False) if native.handles[handle] == lab.INVENTORY else info
        native.info = wrong_acl
        with self.assertRaises(lab.Hold):
            lab.Lab(native).initialize(approved=True)
        self.assertEqual(native.objects[lab.INVENTORY][1], b"")

    def test_mock_syn05_controller_reacquires_then_preserves_crash_residue(self):
        native = self.ready()
        lab.Lab(native).io_trial(approved=True)

        class MemoryProcesses:
            def __init__(self):
                self.started = []
                self.stopped = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                for item in self.started:
                    if item.get("lease"):
                        item["lease"].abandon()

            def spawn(self, mode, *, alternate_cwd):
                item = {"mode": mode}
                self.started.append(item)
                try:
                    item["lease"] = lab.Gate.acquire(native, SID)
                    item["phase"] = "GATE_HELD"
                except lab.Hold as error:
                    self.assert_collision(error)
                    item["phase"] = "GATE_COLLISION"
                if mode == "crash":
                    native.create_dir(lab.WORK_DIRS[1], SID, lab.D_READ | 6 | lab.DELETE)
                    info = lab.Lab(native)._new_file(lab.PARTIAL, SID, SID, lab.F_RW, lab.FRAGMENT)
                    item.update(phase="PARTIAL_READY", partial=list(info.identity),
                                gate=list(item["lease"].initial.identity))
                return item

            @staticmethod
            def assert_collision(error):
                if error.code != "GATE_COLLISION":
                    raise error

            @staticmethod
            def expect(item, phase):
                if item["phase"] != phase:
                    raise lab.Hold("IPC_FAILURE")
                return item

            @staticmethod
            def finish(_item, _code):
                pass

            @staticmethod
            def release(item):
                item["lease"].release()

            def stop_identified(self, item):
                self.stopped.append(item)
                item["lease"].abandon()  # Model OS closing handles after crash.

            @staticmethod
            def private_evidence():
                return {"synthetic": True}

        driver = MemoryProcesses()
        out = lab.Lab(native).concurrent_trial(driver, approved=True)
        self.assertEqual(out["code"], "EXPECTED_CRASH_RESIDUE")
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual([p["mode"] for p in driver.started],
                         ["hold", "contend", "hold", "crash", "contend"])
        self.assertEqual(len(driver.stopped), 1)
        self.assertEqual(native.objects[lab.PARTIAL][1], lab.FRAGMENT)
        self.assertTrue(native.exists(lab.GATE))
        self.assertFalse(native.handles)

    def test_gate_delete_failure_closes_owned_handle_and_preserves_hold(self):
        native = self.ready()
        gate = lab.Gate.acquire(native, SID)
        native.mark_delete = Mock(side_effect=lab.NativeFailure(5))
        with self.assertRaises(lab.NativeFailure):
            gate.release()
        self.assertTrue(native.exists(lab.GATE))
        self.assertFalse(native.handles)

    def test_mock_worker_release_and_interrupted_partial_flow(self):
        native = self.ready()
        events = []
        self.assertEqual(lab.worker(native, "hold", lambda: "release",
                                    lambda phase, **data: events.append(phase), approved=True), 0)
        self.assertEqual(events, ["GATE_HELD", "RELEASED"])
        self.assertFalse(native.exists(lab.GATE))
        with self.assertRaises(lab.Hold):
            lab.worker(native, "crash", lambda: None,
                       lambda phase, **data: events.append(phase), approved=True)
        self.assertEqual(events[-1], "PARTIAL_READY")
        self.assertEqual(native.objects[lab.PARTIAL][1], lab.FRAGMENT)
        self.assertTrue(native.exists(lab.GATE))
        self.assertFalse(native.handles)


class HarnessEntryAndProcessTests(unittest.TestCase):
    def test_direct_worker_entries_require_explicit_execution_intent(self):
        from labs.phase4b2_acl import phase4b2_acl_harness as harness
        native = Mock()
        native.token.side_effect = AssertionError("worker reached Native without intent")
        with self.assertRaises(lab.Hold):
            lab.worker(native, "hold", Mock(), Mock())
        native.token.assert_not_called()
        with patch("labs.phase4b2_acl.phase4b2_acl_native.Win32", side_effect=AssertionError("created write-capable adapter")):
            with self.assertRaises(lab.Hold):
                harness.child_main("hold")

    def test_process_start_requires_intent_and_write_capability_before_popen(self):
        from labs.phase4b2_acl.phase4b2_acl_process import Processes
        for approved, capable in ((False, True), (True, False)):
            native = Mock()
            native.allow_changes = capable
            start = Mock(side_effect=AssertionError("unapproved child start"))
            driver = Processes(native, approved=approved, popen=start)
            with self.subTest(approved=approved, capable=capable), self.assertRaises(lab.Hold):
                driver.spawn("hold", alternate_cwd=False)
            self.assertEqual(start.call_count, 0)

    def test_a_non_crash_worker_cannot_be_terminated_as_p3(self):
        for change in ("role", "designated"):
            driver, child, native = self.child()
            if change == "role":
                child.mode = "hold"
            else:
                driver.crash_child = object()
            with self.subTest(change=change), self.assertRaises(lab.Hold):
                driver.stop_identified(child)
            native.terminate.assert_not_called()

    def test_crash_start_failure_does_not_allow_another_p3_attempt(self):
        from labs.phase4b2_acl.phase4b2_acl_process import Processes
        native = Mock()
        native.allow_changes = True
        start = Mock(side_effect=OSError("synthetic launch failure"))
        driver = Processes(native, approved=True, popen=start)
        with self.assertRaises(OSError):
            driver.spawn("crash", alternate_cwd=False)
        with self.assertRaises(lab.Hold):
            driver.spawn("crash", alternate_cwd=False)
        self.assertEqual(start.call_count, 1)

    def test_preflight_flag_cannot_enable_mutation_and_collision_stays_hold(self):
        from labs.phase4b2_acl import phase4b2_acl_harness as harness
        native = MemoryNative()
        factory, processes = Mock(return_value=native), Mock()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(harness.main(["preflight", "--execute-approved-lab"],
                                          native_factory=factory, process_factory=processes), 0)
        factory.assert_called_once_with(allow_changes=False)
        processes.assert_not_called()
        self.assertFalse(native.objects)
        native._create("", lab.ADMIN, lab.D_READ, True)
        existing = dict(native.objects)
        result = lab.Lab(native).preflight()
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["code"], "ROOT_COLLISION")
        self.assertTrue(result["preflight"]["root_exists"])
        self.assertEqual(native.objects, existing)

    def test_preflight_queries_token_and_only_reports_safe_facts(self):
        native = MemoryNative()
        native.current = lab.Token(SID, False, False)
        out = lab.Lab(native).preflight()
        self.assertEqual(out["preflight"]["token_elevated"], False)
        self.assertEqual(out["preflight"]["root_exists"], False)
        self.assertEqual(out["preflight"]["native_read_checks_completed"], True)
        self.assertFalse(native.objects)
        self.assertFalse(native.handles)
        text = io.StringIO()
        with redirect_stdout(text):
            lab.print_result(out)
        self.assertNotIn(SID, text.getvalue())

    def test_preflight_native_failure_reports_partial_facts_without_mutation(self):
        native = MemoryNative()
        native.current = lab.Token(SID, False, False)
        native.exists = Mock(side_effect=lab.NativeFailure(5))
        out = lab.Lab(native).preflight()
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(out["win32_error_code"], 5)
        self.assertEqual(out["preflight"]["token_elevated"], False)
        self.assertIsNone(out["preflight"]["root_exists"])
        self.assertFalse(native.objects)

    def test_default_plan_and_unapproved_modes_never_instantiate_native(self):
        from labs.phase4b2_acl import phase4b2_acl_harness as harness
        for args, code in (([], 0), (["syn01"], 1), (["syn02"], 1), (["syn05"], 1),
                           (["--secret", SID], 1)):
            factory = Mock(side_effect=AssertionError("must not load Win32"))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(harness.main(args, native_factory=factory), code)
            factory.assert_not_called()
            self.assertNotIn(SID, out.getvalue())

    def test_executable_boundary_suppresses_unexpected_private_errors(self):
        from labs.phase4b2_acl import phase4b2_acl_harness as harness
        factory = Mock(side_effect=RuntimeError(SID + " SDDL private path"))
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(harness.main(["preflight"], native_factory=factory), 1)
        self.assertIn("INTERNAL_ERROR", out.getvalue())
        self.assertNotIn(SID, out.getvalue())
        self.assertNotIn("private path", out.getvalue())

    def child(self):
        from labs.phase4b2_acl.phase4b2_acl_process import Child, Processes
        native = Mock()
        native.allow_changes = True
        native.process_created.return_value = 123
        proc = Mock(pid=456)
        proc.poll.return_value = None
        proc.wait.return_value = 97
        child = Child(proc, object(), 123, "a" * 64, 456, Queue(), "PARTIAL_READY", True, mode="crash")
        driver = Processes(native, approved=True)
        driver.children.append(child)
        driver.crash_child = child
        driver.crash_started = True
        return driver, child, native

    def test_only_authenticated_owned_partial_child_can_be_stopped(self):
        for change in ("foreign", "phase", "pid", "created", "authentication", "exited"):
            driver, child, native = self.child()
            if change == "foreign":
                driver.children.clear()
            elif change == "phase":
                child.phase = "GATE_HELD"
            elif change == "pid":
                child.pid = 99
            elif change == "created":
                native.process_created.return_value = 999
            elif change == "exited":
                child.proc.poll.return_value = 0
            else:
                child.authenticated = False
            with self.subTest(change=change), self.assertRaises(lab.Hold):
                driver.stop_identified(child)
            native.terminate.assert_not_called()
        driver, child, native = self.child()
        driver.stop_identified(child)
        native.terminate.assert_called_once_with(child.handle)
        with self.assertRaises(lab.Hold):
            driver.stop_identified(child)
        native.terminate.assert_called_once_with(child.handle)

    def test_bad_nonce_or_malformed_partial_message_never_authenticates(self):
        for payload in ({"nonce": "wrong", "created": 123, "phase": "PARTIAL_READY"},
                        {"nonce": "a" * 64, "created": 123, "phase": "PARTIAL_READY"}):
            driver, child, native = self.child()
            child.messages.put(payload)
            with self.assertRaises(lab.Hold):
                driver.expect(child, "PARTIAL_READY")
            native.terminate.assert_not_called()


class HarnessSafetyTests(unittest.TestCase):
    def test_wrong_or_unapproved_path_blocks_before_os_access(self):
        for path in ("E:/lab", lab.ROOT + r"\..", lab.ROOT + "-other", ""):
            native = Mock()
            with self.subTest(path=path), self.assertRaises(lab.Hold):
                lab.Lab(native, root=path).preflight()
            native.assert_not_called()
            self.assertEqual(native.mock_calls, [])

    def test_no_approval_blocks_before_native_calls(self):
        native = Mock()
        with self.assertRaises(lab.Hold):
            lab.Lab(native).initialize(approved=False)
        self.assertEqual(native.mock_calls, [])

    def test_non_elevated_initializer_is_blocked(self):
        native = Mock()
        native.token.return_value = lab.Token(SID, False, False)
        with self.assertRaises(lab.Hold) as caught:
            lab.Lab(native).initialize(approved=True)
        self.assertEqual(caught.exception.code, "ADMIN_TOKEN_REQUIRED")
        native.create_dir.assert_not_called()

    def test_existing_root_is_never_reused(self):
        native = Mock()
        native.token.return_value = lab.Token(SID, True, False)
        native.parents.return_value.__enter__ = Mock()
        native.parents.return_value.__exit__ = Mock(return_value=False)
        native.exists.return_value = True
        with self.assertRaises(lab.Hold) as caught:
            lab.Lab(native).initialize(approved=True)
        self.assertEqual(caught.exception.code, "ROOT_COLLISION")
        native.create_dir.assert_not_called()

    def test_denied_access_is_distinct_from_other_native_failures(self):
        for code in (5, 32, 80, 183, 2):
            native = Mock()
            native.open.side_effect = lab.NativeFailure(code)
            if code == 5:
                lab.assert_denied(native, "Config", 2, True)
            else:
                with self.assertRaises(lab.Hold):
                    lab.assert_denied(native, "Config", 2, True)
        native = Mock()
        with self.assertRaises(lab.Hold):
            lab.assert_denied(native, "Config", 2, True)
        native.close.assert_called_once()

    def test_gate_collision_has_no_delete_or_retry(self):
        for code in (80, 183, 32, 5):
            native = Mock()
            native.create_file.side_effect = lab.NativeFailure(code)
            with self.subTest(code=code), self.assertRaises(lab.Hold) as caught:
                lab.Gate.acquire(native, SID)
            self.assertEqual(caught.exception.code,
                             "GATE_COLLISION" if code in (80, 183, 32) else "NATIVE_FAILURE")
            native.create_file.assert_called_once()
            native.mark_delete.assert_not_called()

    def test_release_verifies_identity_and_acl_before_delete(self):
        info = lab.Info((1, "a"), SID, lab.aces(SID, lab.F_RW_DELETE), False, False, 1)
        for changed in (replace(info, identity=(1, "other")),
                        replace(info, protected=False), replace(info, owner=lab.ADMIN)):
            native = Mock()
            native.info.return_value = changed
            lease = lab.Gate(native, 42, info, SID)
            with self.subTest(changed=changed), self.assertRaises(lab.Hold):
                lease.release()
            native.mark_delete.assert_not_called()
            native.close.assert_called_once_with(42)

    def test_failed_work_closes_gate_without_deleting_residue(self):
        native = Mock()
        info = lab.Info((1, "a"), SID, lab.aces(SID, lab.F_RW_DELETE), False, False, 1)
        lease = lab.Gate(native, 42, info, SID)
        lease.abandon()
        lease.abandon()
        native.close.assert_called_once_with(42)
        native.mark_delete.assert_not_called()

    def test_public_error_never_prints_private_native_details(self):
        out = io.StringIO()
        with redirect_stdout(out):
            lab.print_result(lab.result("HOLD", "NATIVE_FAILURE", "SYN-01"))
        self.assertNotIn(SID, out.getvalue())
        self.assertNotIn("SDDL", out.getvalue())
        self.assertEqual(lab.NativeFailure(5).args, ("NATIVE_FAILURE",))
        self.assertNotIn(SID, repr(lab.Token(SID, False, False)))


if __name__ == "__main__":
    unittest.main()
