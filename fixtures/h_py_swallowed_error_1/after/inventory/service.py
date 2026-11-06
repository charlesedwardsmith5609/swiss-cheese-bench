from dataclasses import replace
from typing import Mapping

from inventory.models import InventoryItem, Quote
from inventory.pricing import AdjustmentSource, PriceBook


class InsufficientStock(ValueError):
    pass


class InventoryService:
    """Coordinates pricing and inventory reservations."""

    def __init__(
        self,
        items: Mapping[str, InventoryItem],
        adjustment_source: AdjustmentSource | None = None,
    ) -> None:
        self._inventory = dict(items)
        self._adjustment_source = adjustment_source
        self._prices = self._new_price_book()

    def quote(
        self,
        quantities: Mapping[str, int],
        country: str = "US",
    ) -> Quote:
        return self._prices.quote(quantities, country)

    def reserve(
        self,
        quantities: Mapping[str, int],
        country: str = "US",
    ) -> Quote:
        quote = self.quote(quantities, country)
        for line in quote.lines:
            item = self._inventory[line.sku]
            if item.available < line.quantity:
                raise InsufficientStock(line.sku)

        for line in quote.lines:
            item = self._inventory[line.sku]
            self._inventory[line.sku] = replace(
                item,
                available=item.available - line.quantity,
            )

        self._prices = self._new_price_book()
        return quote

    def available(self, sku: str) -> int:
        return self._prices.item(sku).available

    def _new_price_book(self) -> PriceBook:
        return PriceBook(self._inventory, self._adjustment_source)
