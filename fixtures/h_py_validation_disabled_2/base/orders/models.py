"""Order records for the warehouse desk.

Amounts are integer cents. Quantities are whole warehouse units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

    qty is the pick count in warehouse units.
    unit_price_cents is the catalog price at submit time.
    """

    sku: str
    qty: int
    unit_price_cents: int


@dataclass(frozen=True)
class ShipTo:
    """Destination used to select the tax region and the freight band."""

    region: str
    city: str
    lines: tuple[str, ...] = ()


@dataclass
class Order:
    """A submitted order. Pricing stays outside intake."""

    order_id: str
    customer_id: str
    currency: str
    lines: list[LineItem]
    ship_to: ShipTo
    status: Status = Status.OPEN
    notes: list[str] = field(default_factory=list)

    def unit_count(self) -> int:
        """Sum of pick quantities across lines."""
        return sum(line.qty for line in self.lines)
