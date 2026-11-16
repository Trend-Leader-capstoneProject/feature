"""Structural limits shared by frozen fixture and separately validated live plans."""

from typing import Protocol


class ValidationLimits(Protocol):
    @property
    def max_candidates(self) -> int: ...

    @property
    def max_tool_calls(self) -> int: ...
