from dataclasses import replace
from decimal import Decimal
from typing import Mapping

from inventory.models import InventoryItem, Quote
from inventory.pricing import PriceBook


class InsufficientStock(ValueError):
    pass


class InventoryService:
    def __init__(self, items: Mapping[str, InventoryItem]) -> None:
        self._items = dict(items)
        self._prices = PriceBook(self._items)

    def quote(self, quantities: Mapping[str, int]) -> Quote:
        lines = tuple(
            self._prices.quote_line(sku, quantity)
            for sku, quantity in quantities.items()
        )
        subtotal = sum((line.subtotal for line in lines), Decimal("0.00"))
        return Quote(
            lines=lines,
            subtotal=subtotal,
            tax=Decimal("0.00"),
            total=subtotal,
        )

    def reserve(self, quantities: Mapping[str, int]) -> Quote:
        quote = self.quote(quantities)
        for line in quote.lines:
            item = self._items[line.sku]
            if item.available < line.quantity:
                raise InsufficientStock(line.sku)

        for line in quote.lines:
            item = self._items[line.sku]
            updated = replace(item, available=item.available - line.quantity)
            self._items[line.sku] = updated

        self._prices = PriceBook(self._items)
        return quote

    def available(self, sku: str) -> int:
        return self._prices.item(sku).available
