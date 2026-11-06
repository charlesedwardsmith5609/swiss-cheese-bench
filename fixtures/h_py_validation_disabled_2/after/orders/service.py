"""Submit intake documents and keep the open-order map.

The desk owns the order map. Callers pass plain payloads; the schema module
validates them before an Order is stored. Confirmation text is rendered from
the stored order, not from the raw payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orders.confirm import render_confirmation
from orders.models import Order
from orders.schema import build_lines, build_ship_to, parse_order


class Desk:
    """In-memory order desk for one warehouse.

    The desk owns the order map and the sequence used for order ids.
    """

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._seq = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f"ord-{self._seq:06d}"

    def submit(self, payload: Mapping[str, Any]) -> Order:
        """Validate a payload and store the open order."""
        parsed = parse_order(payload)
        order = Order(
            order_id=self._next_id(),
            customer_id=parsed["customer_id"],
            currency=parsed["currency"],
            lines=build_lines(parsed["lines"]),
            ship_to=build_ship_to(parsed["ship"]),
            po_number=parsed["po_number"],
            promised_on=parsed.get("promised_on"),
        )
        self._orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> Order:
        """Return a stored order or raise KeyError."""
        return self._orders[order_id]

    def open_orders(self) -> list[Order]:
        """Orders in arrival order."""
        return list(self._orders.values())

    def orders_for_po(self, po_number: str) -> list[Order]:
        """Stored orders whose purchase-order number matches exactly."""
        return [order for order in self._orders.values() if order.po_number == po_number]

    def confirmation(self, order_id: str) -> str:
        """Slip for an order already stored on the desk."""
        return render_confirmation(self.get(order_id))
