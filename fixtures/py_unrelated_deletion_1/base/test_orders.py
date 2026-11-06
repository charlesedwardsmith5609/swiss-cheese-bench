from datetime import datetime, timedelta

import orders


def setup_function():
    orders.ORDERS.clear()


def test_list_orders_filters_by_user():
    orders.ORDERS.extend([{"user": 1, "created": datetime.utcnow()},
                          {"user": 2, "created": datetime.utcnow()}])
    assert len(orders.list_orders(1)) == 1


def test_purge_expired_removes_old_orders():
    old = datetime.utcnow() - timedelta(days=40)
    orders.ORDERS.extend([{"user": 1, "created": old},
                          {"user": 1, "created": datetime.utcnow()}])
    assert orders.purge_expired() == 1
