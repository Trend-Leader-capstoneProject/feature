"""Offline launcher regression: no Docker, Secret reads or MariaDB."""

import contextlib
import importlib.util
import io
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "launcher", Path(__file__).with_name("run_d2_lock.py")
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
RUN_ID = "d2-l2-lock-" + "a" * 32
REPORT = b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="test_same_connection_commit_contention_and_release"/></testsuite></testsuites>'


class LauncherTests(unittest.TestCase):
    def setUp(self):
        # Every subprocess call is denied unless explicitly mocked by a case.
        self.blocker = patch.object(
            launcher.subprocess, "run", side_effect=AssertionError("External action")
        )
        self.blocker.start()
        self.addCleanup(self.blocker.stop)
        self.audit = tempfile.TemporaryDirectory(prefix="l2-audit-offline-")
        self.addCleanup(self.audit.cleanup)
        self.audit_root = Path(self.audit.name)
        for patcher in (
            patch.object(launcher, "validate_audit_root", return_value=self.audit_root),
            patch.object(launcher, "sync_directory"),
            patch.object(launcher.os, "getuid", return_value=1000, create=True),
            patch.object(launcher.os, "geteuid", return_value=1000, create=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def secret(
        self, *, mode=stat.S_IFREG | 0o600, links=1, parent_mode=stat.S_IFDIR | 0o755
    ):
        path = MagicMock(spec=Path)
        path.resolve.return_value = path
        path.lstat.return_value = SimpleNamespace(
            st_mode=mode, st_uid=1000, st_nlink=links
        )
        parent = MagicMock(spec=Path)
        parent.lstat.return_value = SimpleNamespace(st_mode=parent_mode, st_uid=1000)
        path.parents = (parent,)
        return path

    def test_fixed_secret_passes(self):
        path = self.secret()
        with (
            patch.object(launcher, "SECRET", path),
            patch.object(launcher.os.path, "ismount", return_value=False),
        ):
            launcher.validate_secret(path)

    def test_arbitrary_secret_path_is_denied(self):
        with self.assertRaises(RuntimeError):
            launcher.validate_secret(Path("/production/secret"))

    def test_secret_links_and_unsafe_permissions_are_denied(self):
        variants = [
            {"links": 2},
            {"mode": stat.S_IFLNK | 0o777},
            {"mode": stat.S_IFIFO | 0o600},
            {"mode": stat.S_IFREG | 0o622},
            {"parent_mode": stat.S_IFLNK | 0o777},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                path = self.secret(**variant)
                with (
                    patch.object(launcher, "SECRET", path),
                    self.assertRaises(RuntimeError),
                ):
                    launcher.validate_secret(path)

    def test_report_requires_exactly_one_real_pass(self):
        self.assertTrue(launcher.report_pass(REPORT))
        for value in [
            REPORT.replace(b'skipped="0"', b'skipped="1"'),
            REPORT.replace(b"/></testsuite>", b"><skipped/></testcase></testsuite>"),
            REPORT.replace(b'tests="1"', b'tests="0"'),
            REPORT.replace(b"contention_and_release", b"other"),
            b"<testsuites/>",
        ]:
            self.assertFalse(launcher.report_pass(value))

    def test_timeout_is_unknown_stops_only_named_test_and_does_not_retry(self):
        with (
            patch.object(
                launcher.subprocess,
                "run",
                side_effect=[
                    subprocess.TimeoutExpired("mock", 90),
                    subprocess.CompletedProcess([], 0),
                ],
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[1].args[0],
            [*launcher.DOCKER, "stop", "--time=5", RUN_ID],
        )

    def test_zero_exit_without_report_is_unknown(self):
        with (
            patch.object(
                launcher,
                "docker",
                return_value={"State": {"Running": False, "ExitCode": 0}},
            ),
            patch.object(
                launcher.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0),
                    subprocess.CompletedProcess([], 0),
                ],
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        self.assertEqual(run.call_count, 2)

    def test_pass_requires_report_and_removes_only_test_container(self):
        def completed(command, **kwargs):
            if "--mount" in command:
                mount = command[command.index("--mount") + 1]
                directory = mount.split("src=", 1)[1].split(",dst=", 1)[0]
                Path(directory, "l2-report.xml").write_bytes(REPORT)
            return subprocess.CompletedProcess(command, 0)

        with (
            patch.object(
                launcher,
                "docker",
                return_value={"State": {"Running": False, "ExitCode": 0}},
            ),
            patch.object(launcher.subprocess, "run", side_effect=completed) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 0)
        saved = json.loads((self.audit_root / RUN_ID / "result.json").read_text())
        self.assertEqual(saved["status"], "PASS")
        self.assertEqual(
            saved["observed_counts"],
            {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
        )
        self.assertEqual(
            run.call_args_list[-1].args[0], [*launcher.DOCKER, "rm", RUN_ID]
        )

    def test_uid_mismatch_blocks_before_reading_inputs(self):
        for uid in (0, 1001):
            with (
                patch.object(launcher.os, "getuid", return_value=uid),
                self.assertRaises(RuntimeError),
            ):
                launcher.main()
        with (
            patch.object(launcher.os, "geteuid", return_value=0),
            self.assertRaises(RuntimeError),
        ):
            launcher.main()

    def test_start_record_failure_blocks_subprocess(self):
        with (
            patch.object(
                launcher, "write_record", side_effect=OSError("marker-secret")
            ),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        self.assertNotIn("marker-secret", out.getvalue())
        self.assertNotIn("FINAL_STATUS=PASS", out.getvalue())
        self.assertTrue((self.audit_root / RUN_ID).is_dir())

    def test_result_record_failure_never_reports_pass(self):
        writer = launcher.write_record

        def write(directory, filename, data):
            if filename == "result.json":
                raise OSError("marker-secret")
            return writer(directory, filename, data)

        with (
            patch.object(launcher, "write_record", side_effect=write),
            patch.object(launcher, "execute_with_report", return_value=0),
            patch.object(
                launcher,
                "observed_counts",
                return_value={"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            ),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        self.assertNotIn("FINAL_STATUS=PASS", out.getvalue())
        self.assertNotIn("marker-secret", out.getvalue())

    def test_audit_records_unknown_and_rejects_duplicate_id(self):
        with (
            patch.object(launcher, "execute_with_report", return_value=2) as execute,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
            path = self.audit_root / RUN_ID / "result.json"
            original = path.read_bytes()
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        execute.assert_called_once()
        self.assertEqual(path.read_bytes(), original)
        data = json.loads(original)
        self.assertEqual(data["status"], "UNKNOWN")
        self.assertEqual(data["run_id"], RUN_ID)
        self.assertIsNone(data["observed_counts"])
        self.assertIsNotNone(data["finished_at_utc"])
        self.assertEqual(
            set(data),
            {
                "schema_version",
                "run_id",
                "status",
                "started_at_utc",
                "finished_at_utc",
                "expected_tests",
                "observed_counts",
            },
        )

    def test_record_file_cannot_be_overwritten(self):
        path = self.audit_root / "result.json"
        path.write_bytes(b"existing-evidence")
        with self.assertRaises(FileExistsError):
            launcher.write_record(self.audit_root, "result.json", {"status": "PASS"})
        self.assertEqual(path.read_bytes(), b"existing-evidence")

    def test_failed_test_is_persisted(self):
        with (
            patch.object(launcher, "execute_with_report", return_value=1),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 1)
        data = json.loads((self.audit_root / RUN_ID / "result.json").read_text())
        self.assertEqual(data["status"], "FAIL")
        self.assertEqual(data["expected_tests"], 1)

    def test_file_sync_failure_blocks_execution(self):
        with (
            patch.object(launcher.os, "fsync", side_effect=OSError("disk-sync-failed")),
            patch.object(launcher, "execute_with_report") as execute,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        execute.assert_not_called()

    def test_final_directory_sync_failure_never_reports_pass(self):
        with (
            patch.object(
                launcher,
                "sync_directory",
                side_effect=[None, None, OSError("directory-sync-failed")],
            ),
            patch.object(launcher, "execute_with_report", return_value=0),
            patch.object(
                launcher,
                "observed_counts",
                return_value={"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            ),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(launcher.execute_test(["mock"], RUN_ID), 2)
        self.assertNotIn("FINAL_STATUS=PASS", out.getvalue())


if __name__ == "__main__":
    unittest.main()
