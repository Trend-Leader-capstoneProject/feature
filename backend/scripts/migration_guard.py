"""Migration guard: exact B-2 preflight only; apply remains disabled."""

from __future__ import annotations

import sys
from collections.abc import Sequence

DENY_DEFAULT = "DENY_DEFAULT"
INVALID_MODE = "INVALID_MODE"
MODE_NOT_ENABLED = "MODE_NOT_ENABLED"
EXIT_DENIED = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Validate syntax before importing the preflight dependencies.

    Guard CLI never prints arguments or environment variables, to avoid
    accidentally reflecting credentials provided by an operator.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if args == ["preflight"]:
        try:
            from scripts.migration_integration import run_preflight

            code, reasons = run_preflight()
        except Exception:
            code, reasons = 4, ("OBSERVATION_FAILED",)
        try:
            if code == 0:
                print("OBSERVED")
            else:
                for reason in reasons:
                    print(reason, file=sys.stderr)
        except Exception:
            # A broken output stream must not expose a traceback or undo the
            # persisted evidence. Do not retry the observation or the output.
            return 4
        return code

    if not args or args == ["deny"]:
        reason = DENY_DEFAULT
    elif args == ["apply"]:
        reason = MODE_NOT_ENABLED
    else:
        reason = INVALID_MODE

    print(reason, file=sys.stderr)
    return EXIT_DENIED


if __name__ == "__main__":
    raise SystemExit(main())
