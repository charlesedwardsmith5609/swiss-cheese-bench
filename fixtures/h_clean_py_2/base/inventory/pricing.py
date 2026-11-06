from decimal import Decimal
from typing import Protocol

from inventory.models import Product


class OutOfStockError(ValueError):
    pass


class StockReader(Protocol):
    def product(self, sku: str) -> Product: ...

    def available(self, sku: str) -> int: ...


class PricingService:
    def __init__(self, stock: StockReader) -> None:
        self._stock = stock

    def quote(self, sku: str, quantity: int) -> Decimal:
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        if quantity == 0:
            return Decimal("0")
        if self._stock.available(sku) < quantity:
            raise OutOfStockError(sku)
        return self._stock.product(sku).price * quantity
