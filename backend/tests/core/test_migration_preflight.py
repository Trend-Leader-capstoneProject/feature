"""Schema observation classification only; no DB or migration fixtures."""

import pytest

from scripts.migration_preflight import classify_schema_state

KNOWN_REVISIONS = frozenset({"initial", "middle", "current"})


@pytest.mark.parametrize(
    (
        "version_table_visible",
        "current_revisions",
        "business_objects_visible",
        "expected",
    ),
    [
        (False, (), False, "UNVERSIONED_EMPTY_CANDIDATE"),
        (False, (), True, "INDETERMINATE"),
        (True, (), False, "INDETERMINATE"),
        (True, (), True, "INDETERMINATE"),
        (True, ("initial",), True, "VERSIONED_OBSERVED"),
        (True, ("middle",), True, "VERSIONED_OBSERVED"),
        (True, ("current",), False, "VERSIONED_OBSERVED"),
        (True, ("unknown",), True, "INDETERMINATE"),
        (True, ("",), False, "INDETERMINATE"),
        (True, ("initial", "current"), True, "INDETERMINATE"),
        (True, ("current", "current"), True, "INDETERMINATE"),
        (False, ("current",), False, "INDETERMINATE"),
        (False, ("current",), True, "INDETERMINATE"),
    ],
)
def test_schema_state_distinguishes_observations(
    version_table_visible, current_revisions, business_objects_visible, expected
):
    assert classify_schema_state(
        version_table_visible=version_table_visible,
        current_revisions=current_revisions,
        business_objects_visible=business_objects_visible,
        known_revisions=KNOWN_REVISIONS,
    ) == expected


def test_revision_must_belong_to_supplied_repository_lineage():
    assert classify_schema_state(
        version_table_visible=True,
        current_revisions=("current",),
        business_objects_visible=True,
        known_revisions=frozenset(),
    ) == "INDETERMINATE"
