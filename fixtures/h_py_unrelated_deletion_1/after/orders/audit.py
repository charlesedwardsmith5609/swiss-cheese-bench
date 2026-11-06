"""Append-only decisions for orders.

The OrderService is the only writer. Readers copy events out; nobody
rewrites an event after record() returns. clerk_id is set when a person
confirmed shipment; other events leave it blank.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str
    order_id: str
    detail: dict[str, object] = field(default_factory=dict)
    clerk_id: str = ""


class AuditLog:
    """In-memory log of place, fulfill, and cancel decisions."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def record(
        self,
        kind: str,
        order_id: str,
        clerk_id: str = "",
        **detail: object,
    ) -> Event:
        event = Event(
            kind=kind,
            order_id=order_id,
            detail=dict(detail),
            clerk_id=clerk_id,
        )
        self._events.append(event)
        return event

    def for_order(self, order_id: str) -> list[Event]:
        return [event for event in self._events if event.order_id == order_id]
