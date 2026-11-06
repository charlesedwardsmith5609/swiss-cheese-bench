"""Catalog quotes for order lines.

PriceBook borrows the catalog mapping owned by OrderService. It does not
copy that mapping. The service is single-threaded and is the only caller.
Amounts are integer cents with no rounding step.
"""

from __future__ import annotations

from dataclasses import dataclass

from orders.models import Line


@dataclass(frozen=True)
class LineQuote:
    """Unit price and extended amount for one line, in integer cents."""

    sku: str
    quantity: int
    unit_cents: int
    amount_cents: int


class PriceBook:
    """SKU unit prices in integer cents."""

    def __init__(self, catalog: dict[str, int]) -> None:
        self._catalog = catalog

    def unit_cents(self, sku: str) -> int:
        """Return the catalog price for sku. Missing keys raise KeyError."""
        return self._catalog[sku]

    def extended_cents(self, unit_cents: int, quantity: int) -> int:
        """Extend a unit price by a quantity. A zero quantity extends to zero."""
        return unit_cents * quantity

    def price_line(self, line: Line) -> LineQuote:
        """Price one line without writing back onto the line object."""
        unit = self.unit_cents(line.sku)
        return LineQuote(
            sku=line.sku,
            quantity=line.quantity,
            unit_cents=unit,
            amount_cents=self.extended_cents(unit, line.quantity),
        )

    def apply(self, lines: list[Line]) -> int:
        """Set unit_cents from the catalog and return the extended total.

        Each line is looked up, updated, and added before the next line is
        read. An unknown SKU raises KeyError from that lookup.
        """
        total = 0
        for line in lines:
            item = self.price_line(line)
            line.unit_cents = item.unit_cents
            total += item.amount_cents
        return total
