"""In-process counters for the dispatcher."""

from __future__ import annotations


class Counter:
    def __init__(self) -> None:
        self._values: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 1:
            raise ValueError("amount must be positive")
        self._values[name] = self._values.get(name, 0) + amount

    def get(self, name: str) -> int:
        return self._values.get(name, 0)
