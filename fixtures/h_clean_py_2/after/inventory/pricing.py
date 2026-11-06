from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from inventory.metrics import PricingMetrics
from inventory.models import Product, QuoteLine, QuoteLineRequest, QuoteRequest


class OutOfStockError(ValueError):
    pass


class CurrencyMismatchError(ValueError):
    pass


class InventoryReader(Protocol):
    def product(self, sku: str) -> Product: ...

    def available(self, sku: str, warehouse: str) -> int: ...


class PricingService:
    def __init__(self, inventory: InventoryReader, metrics: PricingMetrics) -> None:
        self._inventory = inventory
        self._metrics = metrics

    def quote(self, sku: str, quantity: int) -> Decimal:
        request = QuoteRequest(lines=(QuoteLineRequest(sku, quantity),))
        return self.quote_many(request)[0].subtotal

    def quote_many(self, request: QuoteRequest) -> tuple[QuoteLine, ...]:
        try:
            request.validate()
            warehouse = request.normalized_warehouse()
            quoted_lines: list[QuoteLine] = []

            for requested_line in request.lines:
                product = self._inventory.product(requested_line.sku)
                available = self._inventory.available(product.sku, warehouse)
                if available < requested_line.quantity:
                    raise OutOfStockError(product.sku)
                if product.currency != request.currency:
                    raise CurrencyMismatchError(
                        f"{product.sku} is priced in {product.currency}"
                    )

                subtotal = (product.unit_price * requested_line.quantity).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                quoted_lines.append(
                    QuoteLine(
                        sku=product.sku,
                        quantity=requested_line.quantity,
                        unit_price=product.unit_price,
                        subtotal=subtotal,
                    )
                )
        except Exception:
            self._metrics.increment("pricing.quote_failed")
            raise

        self._metrics.increment("pricing.quote_succeeded")
        return tuple(quoted_lines)
