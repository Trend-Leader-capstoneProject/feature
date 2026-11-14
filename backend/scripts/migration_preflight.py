"""Pure B-2 observation rules, not connected to the Guard CLI yet.

This module does not establish an evidence format, reason/exit codes, or
deployment approval. Connection and evidence contracts remain separate gates.
"""

from collections.abc import Collection, Sequence
from typing import Literal

SchemaState = Literal[
    "VERSIONED_OBSERVED", "UNVERSIONED_EMPTY_CANDIDATE", "INDETERMINATE"
]


def classify_schema_state(
    *,
    version_table_visible: bool,
    current_revisions: Sequence[str],
    business_objects_visible: bool,
    known_revisions: Collection[str],
) -> SchemaState:
    """Classify successful reads within the connection's visibility only.

    The caller must supply the actual repository lineage and separately handle
    failed/incomplete reads. Business objects exclude the version table.
    Neither an empty candidate nor a known revision proves schema integrity,
    an empty database, or permission to apply migrations.
    """
    if not version_table_visible:
        if current_revisions or business_objects_visible:
            return "INDETERMINATE"
        return "UNVERSIONED_EMPTY_CANDIDATE"

    if (
        len(current_revisions) == 1
        and current_revisions[0]
        and current_revisions[0] in known_revisions
    ):
        return "VERSIONED_OBSERVED"
    return "INDETERMINATE"
