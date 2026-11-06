'''Tax and freight quotes. Rate-card changes stay out of the order service.'''

from __future__ import annotations

from dataclasses import dataclass

from orders.models import Address, LineItem, line_extension

TAX_RATE: dict[str, float] = {
    'us-west': 0.085,
    'us-east': 0.07,
    'us-central': 0.065,
    'ca-bc': 0.12,
}

FREIGHT: dict[str, float] = {
    'us-west': 6.5,
    'us-east': 8.0,
    'us-central': 7.25,
    'ca-bc': 14.0,
}

FREE_FREIGHT_AT: dict[str, float] = {
    'us-west': 75.0,
    'us-east': 75.0,
    'us-central': 60.0,
    'ca-bc': 120.0,
}

DEFAULT_TAX = 0.08
DEFAULT_FREIGHT = 9.5
DEFAULT_FREE_AT = 80.0


@dataclass(frozen=True)
class PriceQuote:
    '''Priced totals in decimal dollars, already rounded to the cent.'''

    subtotal: float
    tax: float
    shipping: float
    total: float


def quote(lines: list[LineItem], ship_to: Address) -> PriceQuote:
    '''Price merchandise, tax, and freight for one destination.'''
    subtotal = round(sum(line_extension(line) for line in lines), 2)
    rate = TAX_RATE.get(ship_to.region, DEFAULT_TAX)
    tax = round(subtotal * rate, 2)
    if subtotal >= FREE_FREIGHT_AT.get(ship_to.region, DEFAULT_FREE_AT):
        shipping = 0.0
    else:
        shipping = FREIGHT.get(ship_to.region, DEFAULT_FREIGHT)
    total = round(subtotal + tax + shipping, 2)
    return PriceQuote(subtotal=subtotal, tax=tax, shipping=shipping, total=total)
