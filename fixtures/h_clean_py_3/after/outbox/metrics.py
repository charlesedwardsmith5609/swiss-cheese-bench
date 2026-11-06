"""In-process counters for the dispatcher."""

from __future__ import annotations


class Counter:
    """Monotonic named counters."""

    def __init__(self) -> None:
        self._values: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 1:
            raise ValueError("amount must be positive")
        current = self._values.get(name, 0)
        self._values[name] = current + amount

    def get(self, name: str) -> int:
        return self._values.get(name, 0)
