'''Order records accepted by the warehouse desk.

Monetary amounts on an order are decimal dollars rounded to the cent.
Line counts stay in integer warehouse units.
'''

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    '''Lifecycle of a customer order.'''

    OPEN = 'open'
    CANCELLED = 'cancelled'
    FULFILLED = 'fulfilled'


class OrderError(Exception):
    '''The desk rejected an order operation.'''


@dataclass(frozen=True)
class LineItem:
    '''One SKU row on an order.

    qty is the pick count in warehouse units, never a pack multiple.
    unit_price_cents is the catalog price captured at submit time.
    '''

    sku: str
    qty: int
    unit_price_cents: int


@dataclass(frozen=True)
class Address:
    '''Destination used to select the tax region and the freight band.'''

    region: str
    city: str
    lines: tuple[str, ...] = ()


@dataclass
class Order:
    '''A submitted order. Totals are filled in by the pricing step.'''

    order_id: str
    customer_id: str
    lines: list[LineItem]
    ship_to: Address
    status: Status = Status.OPEN
    subtotal: float = 0.0
    tax: float = 0.0
    shipping: float = 0.0
    total: float = 0.0
    notes: list[str] = field(default_factory=list)


def line_extension(item: LineItem) -> float:
    '''Pre-tax line extension in dollars.'''
    return round(item.qty * item.unit_price_cents / 100.0, 2)


def describe_item(item: LineItem) -> str:
    '''Short label used on the pick ticket and in the audit note.'''
    return f'{item.sku} x{item.qty}'
