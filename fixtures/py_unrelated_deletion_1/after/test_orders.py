from datetime import datetime

import orders


def setup_function():
    orders.ORDERS.clear()


def test_list_orders_filters_by_user():
    orders.ORDERS.extend([{"user": 1, "created": datetime.utcnow()},
                          {"user": 2, "created": datetime.utcnow()}])
    assert len(orders.list_orders(1)) == 1


def test_list_orders_respects_limit():
    orders.ORDERS.extend({"user": 1, "created": datetime.utcnow()} for _ in range(5))
    assert len(orders.list_orders(1, limit=2)) == 2
