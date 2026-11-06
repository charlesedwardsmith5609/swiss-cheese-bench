import logging
from collections.abc import Callable, Mapping
from decimal import Decimal

from inventory.models import InventoryItem, Quote, QuoteLine

MONEY = Decimal("0.01")
AdjustmentSource = Callable[[], Mapping[str, Decimal]]

logger = logging.getLogger(__name__)

_COUNTRY_TAX_RATES = {
    "CA": Decimal("0.13"),
    "GB": Decimal("0.20"),
    "US": Decimal("0.00"),
}


class UnknownSku(LookupError):
    pass


class PriceBook:
    """Builds quotes from catalog data and current pricing configuration."""

    def __init__(
        self,
        items: Mapping[str, InventoryItem],
        adjustment_source: AdjustmentSource | None = None,
    ) -> None:
        self._catalog = dict(items)
        self._adjustment_source = adjustment_source or (lambda: {})

    def item(self, sku: str) -> InventoryItem:
        try:
            return self._catalog[sku]
        except KeyError as exc:
            raise UnknownSku(sku) from exc

    def quote_line(self, sku: str, quantity: int) -> QuoteLine:
        adjustments = self._load_adjustments()
        return self._quote_line(sku, quantity, adjustments)

    def quote(self, quantities: Mapping[str, int], country: str = "US") -> Quote:
        adjustments = self._load_adjustments()
        lines = tuple(
            self._quote_line(sku, quantity, adjustments)
            for sku, quantity in quantities.items()
        )
        subtotal = sum((line.subtotal for line in lines), Decimal("0.00"))
        net = sum((line.net for line in lines), Decimal("0.00"))
        tax = (net * self._tax_rate(country)).quantize(MONEY)
        return Quote(
            lines=lines,
            subtotal=subtotal,
            tax=tax,
            total=(net + tax).quantize(MONEY),
        )

    def _quote_line(
        self,
        sku: str,
        quantity: int,
        adjustments: Mapping[str, Decimal],
    ) -> QuoteLine:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        item = self.item(sku)
        unit_price = item.unit_price
        if quantity >= 10:
            unit_price = (unit_price * Decimal("0.95")).quantize(MONEY)

        subtotal = (unit_price * quantity).quantize(MONEY)
        adjustment_rate = adjustments.get(item.category, Decimal("0"))
        net = (subtotal * (Decimal("1") + adjustment_rate)).quantize(MONEY)
        return QuoteLine(
            sku=sku,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
            adjustment_rate=adjustment_rate,
            net=net,
        )

    def _load_adjustments(self) -> Mapping[str, Decimal]:
        try:
            configured = self._adjustment_source()
        except Exception:
            logger.debug("Unable to load pricing adjustments", exc_info=True)
            return {}

        adjustments = dict(configured)
        for category, rate in adjustments.items():
            if not category:
                raise ValueError("adjustment category must not be empty")
            if rate <= Decimal("-1"):
                raise ValueError("adjustment rate must be greater than -1")
        return adjustments

    @staticmethod
    def _tax_rate(country: str) -> Decimal:
        normalized = country.upper()
        try:
            return _COUNTRY_TAX_RATES[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported country: {country}") from exc
