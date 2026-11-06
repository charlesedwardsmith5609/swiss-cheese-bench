"""Idempotent receipt log for accepted webhooks.

A DeliveryLog is owned by the caller. It does not spawn threads and it is not
safe to share across threads without external locking.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Receipt:
    """One accepted delivery.

    ``attempt`` is the partner delivery counter. Senders that omit it, including
    every v1 body, are stored with attempt 1. ``duplicate`` is set by the log.
    """

    event_id: str
    event_type: str
    customer_id: str
    amount_cents: int
    created: int
    api_version: str = ""
    attempt: int = 1
    duplicate: bool = False


class DeliveryLog:
    """Remembers event ids so a replay does not apply twice."""

    def __init__(self) -> None:
        self._receipts: dict[str, Receipt] = {}

    def put(self, receipt: Receipt) -> Receipt:
        existing = self._receipts.get(receipt.event_id)
        if existing is not None:
            return replace(existing, duplicate=True)
        self._receipts[receipt.event_id] = receipt
        return receipt

    def get(self, event_id: str) -> Receipt | None:
        return self._receipts.get(event_id)
