"""Append-only notes for posts and voids.

The ledger owns the log and decides when to append. Amounts are integer cents.
Notes stay in memory for the life of the process.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    kind: str
    number: str
    account_ref: str
    amount_cents: int


class AuditLog:
    """In-memory notes. The log does not interpret kind or amount."""

    def __init__(self) -> None:
        self._notes: list[Note] = []

    def record_post(self, number: str, account_ref: str, amount_cents: int) -> None:
        self._notes.append(Note("post", number, account_ref, amount_cents))

    def record_void(self, number: str, account_ref: str, amount_cents: int) -> None:
        self._notes.append(Note("void", number, account_ref, amount_cents))

    def notes(self) -> tuple[Note, ...]:
        return tuple(self._notes)
