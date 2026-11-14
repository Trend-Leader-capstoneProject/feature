"""P0-B audit is pure and must reject presence, including empty values."""

import pytest

from scripts import migration_environment as environment


def inputs():
    return {key: "value" for key in environment.REQUIRED_INPUTS}


def test_empty_runtime_url_is_rejected():
    assert environment.audit_environment({"DATABASE_URL": ""}) == "ENV_CONFLICT"


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "DB_HOST",
        "DB_ROOT_PASSWORD",
        "API_DB_USER",
        "JWT_SECRET_KEY",
        "MARIADB_ROOT_PASSWORD",
        "MIGRATION_DB_PASSWORD",
        "MIGRATION_DB_URL",
        "MIGRATION_DB_UNKNOWN",
    ],
)
@pytest.mark.parametrize("value", ["", "sensitive-marker"])
def test_forbidden_keys_case_insensitive(key, value):
    assert (
        environment.audit_environment(inputs() | {key.lower(): value}) == "ENV_CONFLICT"
    )


@pytest.mark.parametrize("key", sorted(environment.REQUIRED_INPUTS))
@pytest.mark.parametrize("value", [None, "", " "])
def test_required_inputs(key, value):
    data = inputs()
    if value is None:
        del data[key]
    else:
        data[key] = value
    assert environment.audit_environment(data) == "SETTINGS_INVALID"


def test_allows_os_and_optional_timeout():
    data = inputs() | {
        "PATH": "system",
        "HOME": "home",
        "LANG": "en",
        "MIGRATION_DB_CONNECTION_TIMEOUT": "5",
    }
    assert (
        environment.audit_environment({k.lower(): v for k, v in data.items()}) is None
    )


def test_case_aliases_fail_closed():
    assert (
        environment.audit_environment(inputs() | {"migration_db_host": "other"})
        == "ENV_CONFLICT"
    )
