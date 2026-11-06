import orders


def test_list_orders_filters_by_user():
    orders.ORDERS[:] = [{"user": 1}, {"user": 2}]
    assert len(orders.list_orders(1)) == 1
