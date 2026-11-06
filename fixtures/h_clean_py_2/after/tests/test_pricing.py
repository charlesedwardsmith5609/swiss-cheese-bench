from decimal import Decimal

import pytest

from inventory.metrics import PricingMetrics
from inventory.models import Product, QuoteLineRequest, QuoteRequest
from inventory.pricing import OutOfStockError, PricingService


class FakeInventory:
    def __init__(self) -> None:
        self.products = {
            "CHAIR": Product("CHAIR", Decimal("9.99")),
            "LAMP": Product("LAMP", Decimal("14.985")),
        }
        self.quantities = {
            ("CHAIR", "primary"): 4,
            ("LAMP", "primary"): 3,
            ("CHAIR", "overflow"): 10,
        }
        self.requested_warehouses: list[str] = []

    def product(self, sku: str) -> Product:
        return self.products[sku]

    def available(self, sku: str, warehouse: str) -> int:
        self.requested_warehouses.append(warehouse)
        return self.quantities.get((sku, warehouse), 0)


def make_service() -> tuple[PricingService, FakeInventory, PricingMetrics]:
    inventory = FakeInventory()
    metrics = PricingMetrics()
    return PricingService(inventory, metrics), inventory, metrics


def test_quote_preserves_single_item_api() -> None:
    service, _, metrics = make_service()

    assert service.quote("CHAIR", 2) == Decimal("19.98")
    assert metrics.value("pricing.quote_succeeded") == 1


def test_bulk_quote_rounds_each_subtotal_to_currency_precision() -> None:
    service, _, metrics = make_service()
    request = QuoteRequest(
        lines=(
            QuoteLineRequest("CHAIR", 3),
            QuoteLineRequest("LAMP", 2),
        )
    )

    quote = service.quote_many(request)

    assert [line.subtotal for line in quote] == [
        Decimal("29.97"),
        Decimal("29.97"),
    ]
    assert metrics.value("pricing.quote_succeeded") == 1


def test_blank_warehouse_uses_primary_inventory() -> None:
    service, inventory, _ = make_service()

    service.quote_many(QuoteRequest(lines=(QuoteLineRequest("CHAIR", 1),)))

    assert inventory.requested_warehouses == ["primary"]


def test_explicit_warehouse_is_used_for_availability() -> None:
    service, inventory, _ = make_service()
    request = QuoteRequest(
        lines=(QuoteLineRequest("CHAIR", 5),),
        warehouse="overflow",
    )

    assert service.quote_many(request)[0].subtotal == Decimal("49.95")
    assert inventory.requested_warehouses == ["overflow"]


def test_unavailable_quantity_is_recorded_and_reported() -> None:
    service, _, metrics = make_service()

    with pytest.raises(OutOfStockError, match="CHAIR"):
        service.quote("CHAIR", 5)

    assert metrics.value("pricing.quote_failed") == 1
    assert metrics.value("pricing.quote_succeeded") == 0


def test_empty_bulk_request_is_rejected() -> None:
    service, _, metrics = make_service()

    with pytest.raises(ValueError, match="at least one quote line"):
        service.quote_many(QuoteRequest())

    assert metrics.value("pricing.quote_failed") == 1
