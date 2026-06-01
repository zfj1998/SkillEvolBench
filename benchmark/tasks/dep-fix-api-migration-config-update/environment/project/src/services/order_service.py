"""Order service — legacy engine.execute API."""
from database import engine

def create_order(order_id, user_id, amount):
    engine.execute("INSERT INTO orders (id, user_id, amount) VALUES (:id, :uid, :amt)", {"id": order_id, "uid": user_id, "amt": amount})
    return {"id": order_id, "user_id": user_id, "amount": amount}

def get_order(order_id):
    row = engine.execute("SELECT id, user_id, amount FROM orders WHERE id = :id", {"id": order_id}).fetchone()
    return None if not row else {"id": row[0], "user_id": row[1], "amount": row[2]}

def update_order_amount(order_id, new_amount):
    engine.execute("UPDATE orders SET amount = :amt WHERE id = :id", {"amt": new_amount, "id": order_id})
