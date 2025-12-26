from __future__ import annotations


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        return dict(self._counters)
