'''Desk operations: submit, replace a line, cancel, and list open orders.'''

from __future__ import annotations

from orders.audit import AuditLog
from orders.inventory import Stock
from orders.models import Address, LineItem, Order, OrderError, Status
from orders.pricing import quote


class OrderService:
    '''Submit, reprice, and cancel orders for one warehouse desk.

    The service owns the order map and the per-customer open-order index.
    Stock and the audit log are passed in; stock keeps its own lock.
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

    def submit(
        self,
        customer_id: str,
        lines: list[LineItem],
        ship_to: Address,
        requested_by: str,
    ) -> Order:
        '''Reserve stock, price the order from the rate card, and store it.

        requested_by is the actor written on the submit audit entry.
        '''
        if not lines:
            raise OrderError('an order needs at least one line')
        for line in lines:
            if line.quantity <= 0:
                raise OrderError(f'{line.sku} quantity must be positive')
        order = Order(
            order_id=self._next_id(),
            customer_id=customer_id,
            lines=list(lines),
            ship_to=ship_to,
        )
        priced = quote(order.lines, ship_to)
        order.subtotal = priced.subtotal
        order.tax = priced.tax
        order.shipping = priced.shipping
        order.total = priced.total
        for line in order.lines:
            self._stock.reserve(line.sku, line.quantity)
        self._orders[order.order_id] = order
        self._open_by_customer.setdefault(customer_id, []).append(order.order_id)
        self._audit.record('submit', order.order_id, requested_by)
        return order

    def replace_line(self, order_id: str, index: int, line: LineItem, requested_by: str) -> Order:
        '''Replace one open line, adjust the reservation, and reprice.

        requested_by is recorded on the audit entry for the replacement.
        '''
        order = self._require_open(order_id)
        in_range = index < len(order.lines)
        if not in_range:
            raise OrderError(f'line {index} is outside this order')
        if line.quantity <= 0:
            raise OrderError(f'{line.sku} quantity must be positive')
        previous = order.lines[index]
        if previous.sku != line.sku:
            self._stock.release(previous.sku, previous.quantity)
            self._stock.reserve(line.sku, line.quantity)
        elif line.quantity > previous.quantity:
            self._stock.reserve(line.sku, line.quantity - previous.quantity)
        elif line.quantity < previous.quantity:
            self._stock.release(line.sku, previous.quantity - line.quantity)
        order.lines[index] = line
        priced = quote(order.lines, order.ship_to)
        order.subtotal = priced.subtotal
        order.tax = priced.tax
        order.shipping = priced.shipping
        order.total = priced.total
        self._audit.record('replace', order.order_id, requested_by)
        return order

    def cancel(self, order_id: str, requested_by: str) -> Order:
        '''Release reservations and drop the order from the open index.'''
        order = self._require_open(order_id)
        for line in order.lines:
            self._stock.release(line.sku, line.quantity)
        order.status = Status.CANCELLED
        bucket = self._open_by_customer.get(order.customer_id, [])
        if order_id in bucket:
            bucket.remove(order_id)
        self._audit.record('cancel', order.order_id, requested_by)
        return order

    def list_open(self, customer_id: str) -> list[Order]:
        '''Open orders for one customer, oldest submission first.'''
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
