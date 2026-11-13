"""Migration maintenance entrypoint (Phase B-1: deny by default).

No connection, file read, Alembic import, or migration execution is allowed in
this phase. B-2/B-3 must introduce their own tested preflight/approval paths.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

DENY_DEFAULT = "DENY_DEFAULT"
INVALID_MODE = "INVALID_MODE"
MODE_NOT_ENABLED = "MODE_NOT_ENABLED"
EXIT_DENIED = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Reject every invocation until each explicitly approved mode exists.

    Guard CLI never prints arguments or environment variables, to avoid
    accidentally reflecting credentials provided by an operator.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args == ["deny"]:
        reason = DENY_DEFAULT
    elif args in (["preflight"], ["apply"]):
        # Reserved, not actionable until separately implemented and verified.
        reason = MODE_NOT_ENABLED
    else:
        reason = INVALID_MODE

    print(reason, file=sys.stderr)
    return EXIT_DENIED


if __name__ == "__main__":
    raise SystemExit(main())
