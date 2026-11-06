from decimal import Decimal

import pytest

from inventory.models import Product
from inventory.pricing import OutOfStockError, PricingService


class FakeStock:
    def __init__(self) -> None:
        self.products = {
            "CHAIR": Product("CHAIR", Decimal("9.99")),
        }
        self.quantities = {"CHAIR": 4}

    def product(self, sku: str) -> Product:
        return self.products[sku]

    def available(self, sku: str) -> int:
        return self.quantities.get(sku, 0)


def test_quote_multiplies_price_by_quantity() -> None:
    service = PricingService(FakeStock())

    assert service.quote("CHAIR", 2) == Decimal("19.98")


def test_quote_rejects_unavailable_quantity() -> None:
    service = PricingService(FakeStock())

    with pytest.raises(OutOfStockError):
        service.quote("CHAIR", 5)
