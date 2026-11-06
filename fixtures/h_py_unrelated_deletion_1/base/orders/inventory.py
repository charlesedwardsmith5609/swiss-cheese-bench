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
        held = self._reserved.get(sku, 0)
        return self._on_hand.get(sku, 0) - held

    def reserved(self, sku: str) -> int:
        return self._reserved.get(sku, 0)

    def reserve(self, order: Order) -> None:
        needed = self._totals(order)
        for sku, qty in needed.items():
            if qty > self.available(sku):
                raise InventoryError(sku)
        for sku, qty in needed.items():
            self._reserved[sku] = self._reserved.get(sku, 0) + qty

    def release(self, order: Order) -> None:
        for sku, qty in self._totals(order).items():
            remaining = self._reserved.get(sku, 0) - qty
            if remaining < 0:
                raise InventoryError(sku)
            if remaining == 0:
                self._reserved.pop(sku, None)
            else:
                self._reserved[sku] = remaining

    def _totals(self, order: Order) -> dict[str, int]:
        totals: dict[str, int] = {}
        for line in order.lines:
            totals[line.sku] = totals.get(line.sku, 0) + line.qty
        return totals
