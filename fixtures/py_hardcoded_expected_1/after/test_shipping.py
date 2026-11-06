import pytest

from shipping import shipping_cost


def test_eu_light():
    assert shipping_cost(2.5, "EU") == 7.9


def test_us_heavy():
    assert shipping_cost(10, "US") == pytest.approx(47.5)
