'''Desk operations: submit, replace a line, cancel, and list open orders.'''

from __future__ import annotations

from orders.inventory import Stock
from orders.audit import AuditLog
from orders.models import Address, LineItem, Order, OrderError, Status, line_extension

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


class OrderService:
    '''Submit and cancel orders for one warehouse desk.

    The service owns the order map and the per-customer open-order index.
    Stock and the audit log are passed in and keep their own synchronization.
    '''

    def __init__(self, stock: Stock, audit: AuditLog) -> None:
        self._stock = stock
        self._audit = audit
        self._orders: dict[str, Order] = {}
        self._open_by_customer: dict[str, list[str]] = {}
        self._seq = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f'ord-{self._seq:06d}'

    def _price(
        self, lines: list[LineItem], ship_to: Address
    ) -> tuple[float, float, float, float]:
        '''Merchandise, tax, freight, and total, each rounded to the cent.'''
        subtotal = round(sum(line_extension(line) for line in lines), 2)
        tax = round(subtotal * TAX_RATE.get(ship_to.region, DEFAULT_TAX), 2)
        if subtotal >= FREE_FREIGHT_AT.get(ship_to.region, DEFAULT_FREE_AT):
            shipping = 0.0
        else:
            shipping = FREIGHT.get(ship_to.region, DEFAULT_FREIGHT)
        total = round(subtotal + tax + shipping, 2)
        return subtotal, tax, shipping, total

    def submit(
        self,
        customer_id: str,
        lines: list[LineItem],
        ship_to: Address,
    ) -> Order:
        '''Reserve stock and price a new open order.'''
        if not lines:
            raise OrderError('an order needs at least one line')
        for line in lines:
            if line.qty <= 0:
                raise OrderError(f'{line.sku} qty must be positive')
        order = Order(
            order_id=self._next_id(),
            customer_id=customer_id,
            lines=list(lines),
            ship_to=ship_to,
        )
        subtotal, tax, shipping, total = self._price(order.lines, ship_to)
        order.subtotal = subtotal
        order.tax = tax
        order.shipping = shipping
        order.total = total
        for line in order.lines:
            self._stock.reserve(line.sku, line.qty)
        self._orders[order.order_id] = order
        self._open_by_customer.setdefault(customer_id, []).append(order.order_id)
        self._audit.record('submit', order.order_id, customer_id)
        return order

    def replace_line(self, order_id: str, index: int, line: LineItem) -> Order:
        '''Replace one open line and reprice. Reservations move with the delta.'''
        order = self._require_open(order_id)
        in_range = 0 <= index < len(order.lines)
        if not in_range:
            raise OrderError(f'line {index} is outside this order')
        if line.qty <= 0:
            raise OrderError(f'{line.sku} qty must be positive')
        previous = order.lines[index]
        if previous.sku != line.sku:
            self._stock.release(previous.sku, previous.qty)
            self._stock.reserve(line.sku, line.qty)
        elif line.qty > previous.qty:
            self._stock.reserve(line.sku, line.qty - previous.qty)
        elif line.qty < previous.qty:
            self._stock.release(line.sku, previous.qty - line.qty)
        order.lines[index] = line
        subtotal, tax, shipping, total = self._price(order.lines, order.ship_to)
        order.subtotal = subtotal
        order.tax = tax
        order.shipping = shipping
        order.total = total
        return order

    def cancel(self, order_id: str) -> Order:
        '''Release reservations and drop the order from the open index.'''
        order = self._require_open(order_id)
        for line in order.lines:
            self._stock.release(line.sku, line.qty)
        order.status = Status.CANCELLED
        bucket = self._open_by_customer.get(order.customer_id, [])
        if order_id in bucket:
            bucket.remove(order_id)
        self._audit.record('cancel', order.order_id, order.customer_id)
        return order

    def list_open(self, customer_id: str) -> list[Order]:
        '''Open orders for a customer, in submission order.'''
        ids = self._open_by_customer.get(customer_id, [])
        return [self._orders[order_id] for order_id in ids]

    def _require_open(self, order_id: str) -> Order:
        try:
            order = self._orders[order_id]
        except KeyError as exc:
            raise OrderError(f'unknown order {order_id}') from exc
        if order.status is not Status.OPEN:
            raise OrderError(f'{order_id} is {order.status.value}')
        return order
