"""Existing basic tests for orders."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.order_service import get_order, list_orders


def test_get_order():
    order = get_order("ORD-1002")
    assert order is not None
    assert order["customer"] == "Bob"


def test_list_orders():
    orders = list_orders()
    assert len(orders) == 4


def test_order_not_found():
    order = get_order("INVALID")
    assert order is None
