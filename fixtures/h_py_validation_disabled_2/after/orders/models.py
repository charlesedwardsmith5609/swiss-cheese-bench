"""Order records for the warehouse desk.

Amounts are integer cents. Quantities are whole warehouse units.
Purchase-order numbers are kept as the buyer sent them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Status(Enum):
    """Lifecycle of a customer order."""

    OPEN = "open"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


class OrderError(Exception):
    """The desk rejected an order operation."""


@dataclass(frozen=True)
class LineItem:
    """One SKU row captured at intake.

    quantity is the pick count in warehouse units.
    unit_price_cents is the catalog price at submit time.
    """

    sku: str
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class ShipTo:
    """Destination used to select the tax region and the freight band."""

    region: str
    city: str
    lines: tuple[str, ...] = ()


@dataclass
class Order:
    """A submitted order, including the buyer's purchase-order reference."""

    order_id: str
    customer_id: str
    currency: str
    lines: list[LineItem]
    ship_to: ShipTo
    po_number: str
    promised_on: date | None = None
    status: Status = Status.OPEN
    notes: list[str] = field(default_factory=list)

    def unit_count(self) -> int:
        """Sum of pick quantities across lines."""
        return sum(line.quantity for line in self.lines)

    def confirmation_key(self) -> str:
        """Id printed on the desk slip, stable for a given order and PO."""
        return f"{self.order_id}:{self.po_number}"
