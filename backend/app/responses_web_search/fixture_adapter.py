"""메모리 합성 입력만 제공한다. 전송·환경설정·재시도 기능 없음."""

from dataclasses import dataclass, field

ERROR_KINDS = frozenset({"401", "403", "429", "5xx", "timeout"})


class FixtureUpstreamError(Exception):
    """실제 HTTP/SDK 예외가 아닌 S0의 합성 오류."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(kind)


@dataclass(slots=True)
class FixtureAdapter:
    response: object = None
    error_kind: str | None = None
    calls: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.error_kind is not None and (
            not isinstance(self.error_kind, str)
            or self.error_kind not in ERROR_KINDS
            or self.response is not None
        ):
            raise ValueError("invalid synthetic adapter input")

    def read(self) -> object:
        self.calls += 1
        if self.error_kind is not None:
            raise FixtureUpstreamError(self.error_kind)
        return self.response
