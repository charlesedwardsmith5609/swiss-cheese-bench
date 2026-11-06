"""Order records.

The caller thread owns an OrderService and, through it, these records.
Nothing in this package starts a thread or shares an order across tasks.
Prices and totals are integer cents.
"""

from __future__ import annotations

from dataclasses import dataclass, field


OPEN = "open"
FULFILLED = "fulfilled"
CANCELLED = "cancelled"


@dataclass
class Line:
    """One SKU on an order. quantity is a unit count; prices are cents."""

    sku: str
    quantity: int
    unit_cents: int


@dataclass
class Order:
    """A buyer order. clerk_id is blank until shipment is confirmed."""

    order_id: str
    buyer_id: str
    lines: list[Line] = field(default_factory=list)
    status: str = OPEN
    total_cents: int = 0
    cancel_reason: str = ""
    clerk_id: str = ""


class OrderError(Exception):
    """Base error for a refused order operation."""


class OrderNotFound(OrderError):
    """No order is stored under the given id."""


class OrderStateError(OrderError):
    """The order status does not allow the operation."""


class InventoryError(OrderError):
    """Stock could not be reserved or returned."""
