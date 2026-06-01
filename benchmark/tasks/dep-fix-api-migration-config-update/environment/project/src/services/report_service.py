"""Report service — legacy engine.execute API."""
from database import engine

def count_users():
    return engine.execute("SELECT COUNT(*) FROM users").scalar()

def count_orders():
    return engine.execute("SELECT COUNT(*) FROM orders").scalar()

def total_amount_for_user(user_id):
    return engine.execute("SELECT amount FROM orders WHERE user_id = :uid", {"uid": user_id}).scalar()
