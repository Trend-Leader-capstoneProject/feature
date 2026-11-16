"""Bounded manual one-record CLI. Default validates only, execution is explicit."""

import argparse
import json
from pathlib import Path

from app.services.reviewed_demo_registration import RegistrationBlocked


def main(argv=None):
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--input", required=True)
    arguments.add_argument("--execute", action="store_true")
    args = arguments.parse_args(argv)
    try:
        from sqlalchemy import create_engine

        from app.core.migration_db_config import MigrationDbSettings
        from app.services.reviewed_demo_preflight import dry_run
        from app.services.reviewed_demo_registration import (
            register_one,
            validate_registration,
            verify_registered,
        )
        from scripts.seed_demo_trends import _safe_database_logs

        data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        validate_registration(data)
        if not args.execute:
            print(json.dumps({"status": "REGISTRATION_INPUT_VALIDATED",
                              "dml_executed": False}))
            return 0
        directory = Path(
            "C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-demo-20261117"
        )
        settings = MigrationDbSettings(
            host="127.0.0.1", port=3310, name="trend_leader_demo_review_20261117",
            user="trend_demo_review", password_file=directory / "migration_db_password",
            _env_file=None,
        )
        engine = create_engine(
            settings.connection_url, echo=False, hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        with _safe_database_logs(engine):
            try:
                preflight = dry_run(
                    engine, data=data, app_env="local",
                    expected_target=data["expected_target"],
                )
                if preflight["status"] != "DRY_RUN_READY":
                    raise RegistrationBlocked("DRY_RUN_NOT_READY")
                result = register_one(engine, data)
                try:
                    with engine.connect() as connection:
                        connection.exec_driver_sql("START TRANSACTION READ ONLY")
                        try:
                            result["verification"] = verify_registered(
                                connection, data, result,
                            )
                        finally:
                            connection.rollback()
                except Exception:
                    result["verification"] = {"status": "UNVERIFIED_NO_RETRY"}
            finally:
                engine.dispose()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["verification"]["status"] == "VERIFIED" else 1
    except Exception as error:
        code = (str(error) if isinstance(error, RegistrationBlocked)
                else "REGISTRATION_ERROR")
        print(json.dumps({"status": "BLOCKED", "reason_code": code,
                          "automatic_retry": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
