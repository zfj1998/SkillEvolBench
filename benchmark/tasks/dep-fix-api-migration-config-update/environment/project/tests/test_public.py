from app import initialize
from services.user_service import create_user, get_user
from services.order_service import create_order, get_order
from services.report_service import count_users, count_orders

def test_basic_flow():
    initialize()
    create_user(1, "alice", "a@example.com")
    create_order(10, 1, 120)
    assert get_user(1)["name"] == "alice"
    assert get_order(10)["amount"] == 120
    assert count_users() == 1
    assert count_orders() == 1
