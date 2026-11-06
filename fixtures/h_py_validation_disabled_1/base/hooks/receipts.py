"""Idempotent receipt log for accepted webhooks.

A ReceiptLog is owned by the caller. It does not spawn threads and it is not
safe to share across threads without external locking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    """One accepted delivery."""

    event_id: str
    event_type: str
    customer_id: str
    amount_cents: int
    created: int
    duplicate: bool = False


class ReceiptLog:
    """Remembers event ids so a replay does not apply twice."""

    def __init__(self) -> None:
        self._by_id: dict[str, Receipt] = {}

    def put(self, receipt: Receipt) -> Receipt:
        existing = self._by_id.get(receipt.event_id)
        if existing is not None:
            return Receipt(
                event_id=existing.event_id,
                event_type=existing.event_type,
                customer_id=existing.customer_id,
                amount_cents=existing.amount_cents,
                created=existing.created,
                duplicate=True,
            )
        self._by_id[receipt.event_id] = receipt
        return receipt

    def get(self, event_id: str) -> Receipt | None:
        return self._by_id.get(event_id)
