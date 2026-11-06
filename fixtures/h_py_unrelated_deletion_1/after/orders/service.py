"""Place, fulfill, and cancel orders against a fixed catalog.

Single-threaded. The caller owns the OrderService and the inventory,
audit log, and metrics instances it was constructed with.
"""

from __future__ import annotations

from orders.audit import AuditLog
from orders.inventory import Inventory
from orders.metrics import Metrics
from orders.models import (
    CANCELLED,
    FULFILLED,
    OPEN,
    Line,
    Order,
    OrderNotFound,
    OrderStateError,
)
from orders.pricing import PriceBook


class OrderService:
    """In-memory orders priced in integer cents."""

    def __init__(
        self,
        catalog: dict[str, int],
        inventory: Inventory,
        audit: AuditLog,
        metrics: Metrics,
    ) -> None:
        self._catalog = dict(catalog)
        self._inventory = inventory
        self._audit = audit
        self._metrics = metrics
        self._prices = PriceBook(self._catalog)
        self._orders: dict[str, Order] = {}

    def get(self, order_id: str) -> Order:
        """Return the stored order or raise OrderNotFound."""
        order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    def for_buyer(self, buyer_id: str) -> list[Order]:
        """Orders stored for this buyer, in insertion order."""
        return [
            order for order in self._orders.values() if order.buyer_id == buyer_id
        ]

    def place(self, order_id: str, buyer_id: str, lines: list[Line]) -> Order:
        """Price the lines, reserve stock, and store an open order."""
        if order_id in self._orders:
            raise OrderStateError(order_id)
        if not lines:
            raise OrderStateError("empty")
        order = Order(order_id=order_id, buyer_id=buyer_id, lines=list(lines))
        order.total_cents = self._apply_quote(order)
        self._inventory.reserve(order)
        self._metrics.increment("orders.reservation.held")
        order.status = OPEN
        self._orders[order_id] = order
        self._audit.record(
            "order.placed",
            order_id,
            buyer_id=buyer_id,
            total_cents=order.total_cents,
        )
        return order

    def fulfill(self, order_id: str, clerk_id: str) -> Order:
        """Confirm shipment and store the clerk who confirmed it."""
        order = self.get(order_id)
        if order.status != OPEN:
            raise OrderStateError(order_id)
        order.clerk_id = clerk_id
        order.status = FULFILLED
        self._audit.record(
            "order.fulfilled",
            order_id,
            total_cents=order.total_cents,
            clerk_id=clerk_id,
        )
        return order

    def cancel(self, order_id: str, reason: str) -> Order:
        """Return reserved stock and record why the order was cancelled."""
        order = self.get(order_id)
        if order.status != OPEN:
            raise OrderStateError(order_id)
        self._inventory.release(order)
        order.status = CANCELLED
        order.cancel_reason = reason
        self._audit.record(
            "order.cancelled",
            order_id,
            reason=reason,
            total_cents=order.total_cents,
            line_count=len(order.lines),
        )
        return order

    def _apply_quote(self, order: Order) -> int:
        return self._prices.apply(order.lines)
