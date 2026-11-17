"""D2 host-only launcher. Default: inspect only; --run requires separate approval."""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

PROJECT = "trendleader-d2-isolated-test"
COMPOSE = (
    "/home/ubuntu/trend-leader-d2-isolated-test/compose.d2-isolated-test.yaml.DRAFT"
)
BASE_REVISION = "b6831cf5d855fa5b3b02adaf8a350f83ded86487"
SECRET = Path(
    "/home/ubuntu/trend-leader-d2-isolated-test/secrets/d2_migration_password"
)
DOCKER = ["sudo", "-n", "/usr/bin/docker"]
AUDIT_ROOT = Path("/home/ubuntu/trend-leader-d2-isolated-test/l2-lock-runs")
TEST_TIMEOUT = 90
ENTRYPOINT = ["python", "-m", "pytest", "-c", "/l2/pytest.ini"]


def require(value):
    if not value:
        raise RuntimeError("D2_L2_PRECHECK_FAILED")


def docker(*args):
    result = subprocess.run(
        [*DOCKER, *args], capture_output=True, text=True, check=False, timeout=15
    )
    require(result.returncode == 0)
    return json.loads(result.stdout)[0]


def validate_secret(path):
    require(path == SECRET and path.resolve(strict=True) == SECRET)
    for part in (path, *path.parents):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode))
        require(not info.st_mode & 0o022)
        require(info.st_uid in {0, 1000})
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    require(not os.path.ismount(path))


def validate_uid():
    require(getattr(os, "getuid", lambda: None)() == 1000)
    require(getattr(os, "geteuid", lambda: None)() == 1000)


def validate_audit_root():
    require(AUDIT_ROOT.resolve(strict=True) == AUDIT_ROOT)
    for part in (AUDIT_ROOT, *AUDIT_ROOT.parents):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not info.st_mode & 0o022)
        require(info.st_uid in {0, 1000})
    info = AUDIT_ROOT.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 1000)
    require(stat.S_IMODE(info.st_mode) == 0o700)
    return AUDIT_ROOT


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_record(directory, filename, data):
    # Exclusive creation: a partial record consumes its name too. Never replace.
    descriptor = os.open(
        directory / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(directory)


def observed_counts(report):
    try:
        info = report.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require(info.st_size <= 1024 * 1024)
        root = ET.fromstring(report.read_bytes())
        suites = list(root.iter("testsuite"))
        require(len(suites) == 1)
        counts = {
            key: int(suites[0].get(key))
            for key in ("tests", "failures", "errors", "skipped")
        }
        require(all(value >= 0 for value in counts.values()))
        require(counts["tests"] == len(list(root.iter("testcase"))))
        return counts
    except Exception:  # noqa: BLE001 - unknown counts, no raw XML/exception
        return None


def source_hash(directory):
    digest = hashlib.sha256()
    for name in ("test_connection_lock.py", "pytest.ini"):
        digest.update(name.encode() + b"\0" + (directory / name).read_bytes())
    return digest.hexdigest()


def report_pass(data):
    # Inspect only structural counts; never print XML or exception text.
    require(len(data) <= 1024 * 1024)
    root = ET.fromstring(data)
    cases = root.findall(".//testcase")
    return (
        len(cases) == 1
        and cases[0].get("name") == "test_same_connection_commit_contention_and_release"
        and not list(root.iter("failure"))
        and not list(root.iter("error"))
        and not list(root.iter("skipped"))
        and all(
            s.get("tests") == "1"
            and s.get("failures") == "0"
            and s.get("errors") == "0"
            and s.get("skipped") == "0"
            for s in root.iter("testsuite")
        )
        and bool(root.findall(".//testsuite"))
    )


def execute_test(command, name):
    counts = None
    started = datetime.now(UTC).isoformat()
    try:
        validate_uid()
        require(re.fullmatch(r"d2-l2-lock-[0-9a-f]{32}", name))
        root = validate_audit_root()
        directory = root / name
        directory.mkdir(mode=0o700, exist_ok=False)
        sync_directory(root)
        record = {
            "schema_version": 1,
            "run_id": name,
            "status": "UNKNOWN",
            "started_at_utc": started,
            "finished_at_utc": None,
            "expected_tests": 1,
            "observed_counts": None,
        }
        write_record(directory, "started.json", record)
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        print("D2_L2_RECORD_FAILED_TEST_NOT_STARTED_NO_RETRY")
        return 2
    print("D2_L2_RUN_ID=" + name, flush=True)
    code = 2
    try:
        # A host scratch bind survives container exit; container tmpfs does not.
        with tempfile.TemporaryDirectory(prefix="d2-l2-results-") as scratch:
            command = list(command)
            command[-1:-1] = ["--mount", f"type=bind,src={scratch},dst=/results"]
            report = Path(scratch) / "l2-report.xml"
            code = execute_with_report(command, name, report)
            counts = observed_counts(report)
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        code = 2
    record.update(
        status={0: "PASS", 1: "FAIL", 2: "UNKNOWN"}[code],
        finished_at_utc=datetime.now(UTC).isoformat(),
        observed_counts=counts,
    )
    try:
        require(
            code != 0
            or counts == {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}
        )
        write_record(directory, "result.json", record)
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        print("D2_L2_RECORD_FAILED_RESULT_UNKNOWN_NO_RETRY")
        return 2
    print("D2_L2_FINAL_STATUS=" + record["status"])
    return code


def execute_with_report(command, name, report):
    try:
        result = subprocess.run(
            command, capture_output=True, check=False, timeout=TEST_TIMEOUT
        )
        state = docker("container", "inspect", name)["State"]
        require(not state["Running"] and state["ExitCode"] == result.returncode)
        if result.returncode == 1:
            print("D2_L2_TEST_FAILED_NO_RETRY")
            return 1
        require(result.returncode == 0 and not state.get("OOMKilled"))
        info = report.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require(info.st_size <= 1024 * 1024)
        require(report_pass(report.read_bytes()))
        removed = subprocess.run(
            [*DOCKER, "rm", name], capture_output=True, check=False, timeout=15
        )
        require(removed.returncode == 0)
        return 0
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - no raw exceptions
        # Stop only this unique test container, never DB/Compose or another run.
        # Killing the CLI on timeout alone would leave the DB sessions alive.
        try:
            stopped = subprocess.run(
                [*DOCKER, "stop", "--time=5", name],
                capture_output=True,
                check=False,
                timeout=15,
            )
            require(stopped.returncode == 0)
        except (Exception, KeyboardInterrupt):  # noqa: BLE001
            print("D2_L2_STOP_UNCONFIRMED")
        print("D2_L2_RESULT_UNKNOWN_NO_RETRY_CHECK_RUN_ID")
        return 2


def main():
    validate_uid()
    validate_audit_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, default=SECRET)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    # Approval JSON contains identifiers only, never credentials or URLs.
    approved = json.loads(args.approval.read_text(encoding="utf-8"))
    require(
        set(approved)
        == {
            "ALLOWED_HOST",
            "ALLOWED_PORT",
            "ALLOWED_DB_IP",
            "ALLOWED_CURRENT_USER",
            "ALLOWED_SERVER_HOSTNAME",
            "ALLOWED_SERVER_ID",
            "ALLOWED_VOLUME",
            "ALLOWED_NETWORK",
            "ALLOWED_NETWORK_KEY",
            "ALLOWED_DB_CONTAINER",
            "ALLOWED_DB_IMAGE_DIGEST",
        }
    )
    require(all(isinstance(v, str) and v and v == v.strip() for v in approved.values()))
    require(approved["ALLOWED_HOST"] == "db")
    require(approved["ALLOWED_PORT"] == "3306")
    require(approved["ALLOWED_DB_CONTAINER"] == PROJECT + "-db-1")
    require(approved["ALLOWED_NETWORK"] == PROJECT + "_d2_net")
    require(approved["ALLOWED_NETWORK_KEY"] == "d2_net")
    require(approved["ALLOWED_VOLUME"] == PROJECT + "_d2_db_data")
    require(approved["ALLOWED_CURRENT_USER"].startswith("d2_migrator@"))
    validate_secret(args.secret_file)
    require(args.image_id.startswith("sha256:") and len(args.image_id) == 71)
    db = docker("container", "inspect", approved["ALLOWED_DB_CONTAINER"])
    labels = db["Config"]["Labels"]
    require(labels.get("com.docker.compose.project") == PROJECT)
    require(labels.get("com.docker.compose.service") == "db")
    require(labels.get("com.docker.compose.project.config_files") == COMPOSE)
    require(db["State"]["Running"])
    db_image = docker("image", "inspect", db["Image"])
    require(
        any(
            digest.split("@")[-1] == approved["ALLOWED_DB_IMAGE_DIGEST"]
            for digest in (db_image.get("RepoDigests") or [])
        )
    )
    require(not db["HostConfig"]["PortBindings"])
    require(all(not v for v in db["NetworkSettings"]["Ports"].values()))
    networks = db["NetworkSettings"]["Networks"]
    require(set(networks) == {approved["ALLOWED_NETWORK"]})
    endpoint = networks[approved["ALLOWED_NETWORK"]]
    require(endpoint["IPAddress"] == approved["ALLOWED_DB_IP"])
    require("db" in endpoint["Aliases"])
    volumes = [m for m in db["Mounts"] if m["Destination"] == "/var/lib/mysql"]
    require(len(volumes) == 1 and volumes[0]["Type"] == "volume")
    require(volumes[0]["Name"] == approved["ALLOWED_VOLUME"])
    network = docker("network", "inspect", approved["ALLOWED_NETWORK"])
    require(network["Internal"] and network["Driver"] == "bridge")
    require(network["Id"] == endpoint["NetworkID"])
    require(network["Labels"].get("com.docker.compose.project") == PROJECT)
    require(
        network["Labels"].get("com.docker.compose.network")
        == approved["ALLOWED_NETWORK_KEY"]
    )
    # Refuse unexpected attached services before creating any test container.
    require(set(network["Containers"]) == {db["Id"]})
    image = docker("image", "inspect", args.image_id)
    require(image["Id"] == args.image_id)
    require(image["Os"] == "linux" and image["Architecture"] == "amd64")
    require(image["Config"]["Entrypoint"] == ENTRYPOINT)
    require(
        image["Config"]["Cmd"]
        == [
            "/l2/test_connection_lock.py",
            "--confcutdir=/l2",
            "-m",
            "integration",
            "-q",
            "--tb=no",
            "--show-capture=no",
            "-p",
            "no:cacheprovider",
            "--junitxml=/results/l2-report.xml",
        ]
    )
    require(image["Config"]["User"] == "1000:1000")
    image_labels = image["Config"]["Labels"]
    require(image_labels.get("trendleader.l2.base-revision") == BASE_REVISION)
    source = (
        Path(__file__).resolve().parents[2]
        / "backend/tests/l2_lock/test_connection_lock.py"
    )
    require(
        image_labels.get("trendleader.l2.test-sha256")
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    require(
        image_labels.get("trendleader.l2.source-sha256") == source_hash(source.parent)
    )
    if not args.run:
        print("D2_L2_PREFLIGHT_OK_TEST_NOT_RUN")
        return 0
    name = "d2-l2-lock-" + uuid4().hex
    command = [
        *DOCKER,
        "run",
        "--name",
        name,
        "--pull=never",
        "--read-only",
        "--network",
        network["Id"],
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
        "--mount",
        f"type=bind,src={args.secret_file},dst=/run/secrets/d2_migrator,readonly",
    ]
    environ = {
        "RUN": "D2_LOCK_TEST_APPROVED",
        "HOST": "db",
        "PORT": "3306",
        "PASSWORD_FILE": "/run/secrets/d2_migrator",
    }
    environ.update(
        {
            k: approved[k]
            for k in (
                "ALLOWED_HOST",
                "ALLOWED_PORT",
                "ALLOWED_DB_IP",
                "ALLOWED_CURRENT_USER",
                "ALLOWED_SERVER_HOSTNAME",
                "ALLOWED_SERVER_ID",
            )
        }
    )
    for key, value in environ.items():
        command.extend(["--env", "L2_LOCK_" + key + "=" + value])
    command.append(args.image_id)
    # Dedicated image's own ENTRYPOINT/CMD; never override the Guard entrypoint.
    return execute_test(command, name)


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001 - never expose Docker/credential exceptions
        print("D2_L2_PRECHECK_OR_EXECUTION_FAILED")
        code = 1
    raise SystemExit(code)
