from decimal import Decimal
from typing import Mapping

from inventory.models import InventoryItem, QuoteLine

MONEY = Decimal("0.01")


class UnknownSku(LookupError):
    pass


class PriceBook:
    def __init__(self, items: Mapping[str, InventoryItem]) -> None:
        self._items = dict(items)

    def item(self, sku: str) -> InventoryItem:
        try:
            return self._items[sku]
        except KeyError as exc:
            raise UnknownSku(sku) from exc

    def quote_line(self, sku: str, quantity: int) -> QuoteLine:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        item = self.item(sku)
        unit_price = item.unit_price
        if quantity >= 10:
            unit_price = (unit_price * Decimal("0.95")).quantize(MONEY)

        return QuoteLine(
            sku=sku,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=(unit_price * quantity).quantize(MONEY),
        )
