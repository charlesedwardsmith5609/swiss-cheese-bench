"""Process-local counters for the upload service.

The thread that constructs a Counter owns its value. Other threads must not
share an instance.
"""

from __future__ import annotations


class Counter:
    """Monotonic integer counter."""

    def __init__(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("counter name is required")
        self.name = name.strip()
        self.value = 0

    def increment(self, amount: int = 1) -> None:
        """Record one or more occurrences."""
        if amount < 1:
            raise ValueError("amount must be positive")
        self.value += amount
