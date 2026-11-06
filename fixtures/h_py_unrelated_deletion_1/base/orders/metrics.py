"""Counters for reservation traffic.

The OrderService is the only writer. Callers may read a snapshot; reading
does not reset a counter.
"""

from __future__ import annotations


class Metrics:
    """Named integer counters. A missing name reads as zero."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        self._counts[name] = self._counts.get(name, 0) + amount

    def value(self, name: str) -> int:
        return self._counts.get(name, 0)

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)
