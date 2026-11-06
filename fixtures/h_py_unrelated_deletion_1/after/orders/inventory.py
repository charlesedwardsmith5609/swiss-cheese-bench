"""Stock reserved for open orders.

The OrderService that built this Inventory is the only mutator. On-hand
counts are fixed for the life of the object.
"""

from __future__ import annotations

from orders.models import InventoryError, Order


class Inventory:
    """Available units are on-hand minus reserved."""

    def __init__(self, on_hand: dict[str, int]) -> None:
        self._on_hand = dict(on_hand)
        self._reserved: dict[str, int] = {}

    def available(self, sku: str) -> int:
        """Units of sku that are on hand and not reserved."""
        held = self._reserved.get(sku, 0)
        return self._on_hand.get(sku, 0) - held

    def reserved(self, sku: str) -> int:
        return self._reserved.get(sku, 0)

    def reserve(self, order: Order) -> None:
        """Hold every line on the order, or hold none of them."""
        needed = self._totals(order)
        for sku, quantity in needed.items():
            if quantity > self.available(sku):
                raise InventoryError(sku)
        for sku, quantity in needed.items():
            self._reserved[sku] = self._reserved.get(sku, 0) + quantity

    def release(self, order: Order) -> None:
        """Return a cancelled order's units to the available pool."""
        for sku, quantity in self._totals(order).items():
            remaining = self._reserved.get(sku, 0) - quantity
            if remaining < 0:
                raise InventoryError(sku)
            if remaining == 0:
                self._reserved.pop(sku, None)
            else:
                self._reserved[sku] = remaining

    def _totals(self, order: Order) -> dict[str, int]:
        totals: dict[str, int] = {}
        for line in order.lines:
            totals[line.sku] = totals.get(line.sku, 0) + line.quantity
        return totals
