"""Reviewed Daily JSON CLI: read-only by default, interactive write by approval."""

import argparse
import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path

from app.services.reviewed_demo_registration import TARGET, RegistrationBlocked


def _show(payload, *, stderr=False):
    output = sys.stderr if stderr else sys.stdout
    print(
        json.dumps(payload, ensure_ascii=False, default=str),
        file=output, flush=True,
    )


def _open_receipt(path):
    stream = None
    try:
        stream = path.open("a+", encoding="utf-8")
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RegistrationBlocked("RECEIPT_MUST_BE_REGULAR_FILE")
        stream.seek(0)
        for line in stream:
            if (not line.endswith("\n")
                    or not isinstance(json.loads(line), dict)):
                raise RegistrationBlocked("RECEIPT_FORMAT_INVALID")
        stream.seek(0, os.SEEK_END)
        stream.flush()
        os.fsync(stream.fileno())
        return stream
    except Exception as error:
        if stream is not None:
            stream.close()
        if isinstance(error, RegistrationBlocked):
            raise
        raise RegistrationBlocked("RECEIPT_NOT_APPENDABLE") from None


def _save_receipt(stream, receipt):
    stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--receipt-file")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    receipt_stream = None
    try:
        from sqlalchemy import create_engine

        from app.core.migration_db_config import MigrationDbSettings
        from app.services.reviewed_demo_daily_registration import (
            preflight_batch,
            register_candidate,
            validate_batch,
            verify_candidate,
        )

        batch = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        candidates = validate_batch(batch)
        repository_dir = Path(__file__).resolve().parents[2]
        password_path = Path(args.password_file).resolve()
        if password_path.is_relative_to(repository_dir):
            raise RegistrationBlocked("PASSWORD_MUST_BE_OUTSIDE_REPOSITORY")
        if args.execute:
            if not args.receipt_file:
                raise RegistrationBlocked("RECEIPT_FILE_REQUIRED")
            receipt_path = Path(args.receipt_file).resolve()
            if receipt_path.is_relative_to(repository_dir):
                raise RegistrationBlocked("RECEIPT_MUST_BE_OUTSIDE_REPOSITORY")
            if not receipt_path.parent.is_dir():
                raise RegistrationBlocked("RECEIPT_DIRECTORY_MISSING")
            if receipt_path in (password_path, Path(args.input).resolve()):
                raise RegistrationBlocked("RECEIPT_INPUT_PATH_CONFLICT")
            if receipt_path.exists() and not receipt_path.is_file():
                raise RegistrationBlocked("RECEIPT_MUST_BE_REGULAR_FILE")

        settings = MigrationDbSettings(
            host=TARGET["host"], port=TARGET["port"],
            name=TARGET["database"], user="trend_demo_review",
            password_file=password_path, _env_file=None,
        )
        engine = create_engine(
            settings.connection_url, echo=False, hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        preflight = preflight_batch(engine, batch)
        _show(preflight)
        if preflight["status"] != "DRY_RUN_READY":
            return 1
        if not args.execute:
            return 0

        if not sys.stdin.isatty():
            raise RegistrationBlocked("INTERACTIVE_CONFIRMATION_REQUIRED")
        approval = f"REGISTER {len(candidates)}"
        print(
            f"Type '{approval}' to register {len(candidates)} records "
            "to the ISOLATED demo database:",
            flush=True,
        )
        if input().strip() != approval:
            raise RegistrationBlocked("OPERATOR_CONFIRMATION_REQUIRED")
        receipt_stream = _open_receipt(receipt_path)
        approved_at = datetime.now().astimezone().isoformat()
        completed = 0
        for candidate in candidates:
            try:
                receipt = register_candidate(engine, candidate)
            except RegistrationBlocked as error:
                _show({
                    "status": "BLOCKED", "position": candidate.position,
                    "reason_code": str(error), "automatic_retry": False,
                }, stderr=True)
                return 1
            receipt["reviewer_alias"] = batch["reviewer_alias"]
            receipt["operator_approved_at"] = approved_at
            try:
                receipt["verification"] = verify_candidate(
                    engine, candidate, receipt,
                )
            except Exception:
                receipt["verification"] = {
                    "status": "UNVERIFIED_NO_RETRY",
                }
            _show(receipt)
            try:
                _save_receipt(receipt_stream, receipt)
            except Exception:
                raise RegistrationBlocked(
                    "RECEIPT_WRITE_FAILED_NO_RETRY"
                ) from None
            if receipt["verification"]["status"] != "VERIFIED":
                raise RegistrationBlocked(
                    "POST_COMMIT_UNVERIFIED_NO_RETRY"
                )
            completed += 1
        try:
            receipt_stream.close()
        except Exception:
            raise RegistrationBlocked("RECEIPT_WRITE_FAILED_NO_RETRY") from None
        receipt_stream = None
        _show({
            "status": "BATCH_VERIFIED",
            "committed_count": completed,
            "receipt_file": str(receipt_path),
        })
        return 0
    except RegistrationBlocked as error:
        _show({
            "status": "BLOCKED", "reason_code": str(error),
            "automatic_retry": False,
        }, stderr=True)
        return 1
    except Exception:
        _show({
            "status": "BLOCKED", "reason_code": "DAILY_CLI_ERROR",
            "automatic_retry": False,
        }, stderr=True)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
        if receipt_stream is not None:
            try:
                receipt_stream.close()
            except Exception:
                _show({
                    "status": "BLOCKED",
                    "reason_code": "RECEIPT_WRITE_FAILED_NO_RETRY",
                    "automatic_retry": False,
                }, stderr=True)


if __name__ == "__main__":
    raise SystemExit(main())
