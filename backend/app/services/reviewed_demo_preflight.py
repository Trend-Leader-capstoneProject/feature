"""Reviewed Demo dry-run. No DML, Session, flush, commit or publication."""

from app.external_trends.normalizer import normalize_source_url, normalize_title
from app.models.db_enums import TrendSourcePlatform
from app.repositories.reviewed_demo_repository import ReviewedDemoRepository


def validate_reviewed_input(data):
    """Require a separately authored human review record, never a Live envelope."""
    if not isinstance(data, dict) or data.get("input_kind") != "REVIEWED_DEMO":
        raise ValueError("INVALID_REVIEWED_INPUT")
    fields = {"title": 255, "source_title": 255, "source_url": 4096,
              "reviewer": 100, "review_note": 2000}
    if any(not isinstance(data.get(key), str) or not data[key].strip()
           or len(data[key]) > limit for key, limit in fields.items()):
        raise ValueError("INVALID_REVIEWED_INPUT")
    if data.get("original_failure") != "CITATION_URL_MISMATCH":
        raise ValueError("ORIGINAL_FAILURE_REQUIRED")
    title = normalize_title(data["title"])
    url = normalize_source_url(data["source_url"])
    if title is None or url is None:
        raise ValueError("INVALID_TITLE_OR_URL")
    category_id = data.get("category_id")
    if category_id is not None and (type(category_id) is not int or category_id < 1):
        raise ValueError("INVALID_CATEGORY_ID")
    if data.get("platform") not in {item.value for item in TrendSourcePlatform}:
        raise ValueError("INVALID_PLATFORM")
    return title, url


def dry_run(engine, *, data, app_env, expected_target=None):
    """Observe identity, categories and duplicates in one rolled-back read-only txn."""
    title, url = validate_reviewed_input(data)
    report = {
        "mode": "READ_ONLY_DRY_RUN", "status": "BLOCKED",
        "dml_allowed": False, "automatic_validation": "CITATION_URL_MISMATCH",
        "publication_status": "NOT_FOR_PUBLICATION", "g5_g6": "HOLD",
        "blockers": [], "categories": [], "duplicates": None,
        "identity": None,
        "plan": {
            "transaction": "ONE_BATCH_ATOMIC_REVALIDATE_BEFORE_WRITE",
            "steps": ["VERIFY_APPROVED_CONNECTION", "RECHECK_REVIEW_AND_CATEGORY",
                      "RECHECK_DUPLICATES", "INSERT_TREND_AND_FLUSH_ID",
                      "INSERT_SOURCE", "INSERT_CATEGORY_MAP", "COMMIT_ONCE"],
            "failure_action": "ROLLBACK_ALL",
            "row_counts": {"Trend": 1, "TrendSource": 1, "TrendCategoryMap": 1},
            "proposed_title": title.display_title,
            "normalized_title": title.normalized_title,
            "source_key": url.source_key,
            "category_id": data.get("category_id"), "platform": data["platform"],
        },
    }
    target = engine.url
    if not expected_target:
        report["blockers"].append("ISOLATED_TARGET_UNCONFIRMED")
    if (
        app_env != "local" or target.drivername != "mysql+pymysql"
        or not target.host or target.port is None or not target.database
        or set(target.query) - {"charset"}
    ):
        report["blockers"].append("UNSUPPORTED_DEVELOPMENT_TARGET")
        return report
    report["configured_target"] = {
        "host": target.host, "port": target.port, "database": target.database,
        "environment": app_env,
    }
    try:
        with engine.connect() as connection:
            try:
                connection.exec_driver_sql("START TRANSACTION READ ONLY")
                repository = ReviewedDemoRepository(connection)
                identity = repository.identity()
                report["identity"] = identity
                observed = {"host": target.host, "port": target.port,
                            "database": identity["database_name"],
                            "current_user": identity["current_user"]}
                if identity["database_name"] != target.database:
                    report["blockers"].append("DATABASE_IDENTITY_MISMATCH")
                    return report
                if expected_target and observed != expected_target:
                    report["blockers"].append("ISOLATED_TARGET_UNCONFIRMED")
                report["categories"] = repository.categories()
                if data.get("category_id") not in {
                    row["category_id"] for row in report["categories"]
                }:
                    report["blockers"].append("ACTIVE_IT_CHILD_SELECTION_REQUIRED")
                report["duplicates"] = repository.duplicates(
                    title=title.display_title, normalized_title=title.normalized_title,
                    source_key=url.source_key, source_url=data["source_url"],
                    canonical_url=url.canonical_url,
                )
                if (report["duplicates"]["title_trend_ids"]
                        or report["duplicates"]["source_trend_ids"]):
                    report["blockers"].append("EXISTING_DATA_CONFLICT")
                report["schema_issues"] = repository.schema_issues()
                if report["schema_issues"]:
                    report["blockers"].append("MODEL_SCHEMA_MISMATCH")
            finally:
                connection.rollback()
    except Exception as error:
        code = getattr(getattr(error, "orig", None), "args", ())
        report["database_error_code"] = (
            code[0] if code and type(code[0]) is int else None
        )
        report["blockers"].append(
            "DATABASE_AUTHENTICATION_FAILED" if code and code[0] == 1045
            else "DATABASE_INSPECTION_FAILED"
        )
        return report
    report["status"] = "BLOCKED" if report["blockers"] else "DRY_RUN_READY"
    return report
