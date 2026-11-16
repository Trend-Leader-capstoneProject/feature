"""Explicit read-only Reviewed Demo CLI. No write mode."""

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv=None):
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--input", required=True)
    arguments.add_argument("--env-file", required=True)
    arguments.add_argument("--host")
    arguments.add_argument("--port", type=int)
    args = arguments.parse_args(argv)
    try:
        from dotenv import dotenv_values
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL, make_url

        from app.services.reviewed_demo_preflight import (
            dry_run,
            validate_reviewed_input,
        )
        from scripts.seed_demo_trends import _safe_database_logs

        data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        validate_reviewed_input(data)
        values = dotenv_values(Path(args.env_file))

        def setting(key, default=None):
            return os.environ.get(key, values.get(key, default))

        database_url = setting("DATABASE_URL")
        if not database_url:
            host = args.host or setting("DB_HOST")
            if not host or not all(setting(key) for key in (
                "DB_NAME", "DB_USER", "DB_PASSWORD",
            )):
                raise ValueError("DB_CONFIGURATION_REQUIRED")
            database_url = URL.create(
                "mysql+pymysql", host=host,
                port=int(setting("DB_PORT", "3306")), database=setting("DB_NAME"),
                username=setting("DB_USER"), password=setting("DB_PASSWORD"),
                query={"charset": "utf8mb4"},
            )
        database_url = make_url(database_url)
        overrides = {}
        if args.host:
            overrides["host"] = args.host
        if args.port is not None:
            if not 1 <= args.port <= 65535:
                raise ValueError("INVALID_PORT")
            overrides["port"] = args.port
        database_url = database_url.set(**overrides)
        engine = create_engine(
            database_url, echo=False, hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        with _safe_database_logs(engine):
            try:
                report = dry_run(
                    engine, data=data, app_env=setting("APP_ENV", "local"),
                    expected_target=data.get("expected_target"),
                )
            finally:
                engine.dispose()
        print(json.dumps(report, ensure_ascii=False, default=str))
        return 0 if report["status"] == "DRY_RUN_READY" else 1
    except Exception:
        print(json.dumps({
            "status": "BLOCKED", "blockers": ["DRY_RUN_INPUT_OR_CONFIG_ERROR"],
            "dml_allowed": False,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
