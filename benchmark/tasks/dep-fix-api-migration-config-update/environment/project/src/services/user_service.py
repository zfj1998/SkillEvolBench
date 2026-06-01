"""User service — legacy engine.execute API."""
from database import engine

def create_user(user_id, name, email):
    engine.execute("INSERT INTO users (id, name, email) VALUES (:id, :name, :email)", {"id": user_id, "name": name, "email": email})
    return {"id": user_id, "name": name, "email": email}

def get_user(user_id):
    row = engine.execute("SELECT id, name, email FROM users WHERE id = :id", {"id": user_id}).fetchone()
    return None if not row else {"id": row[0], "name": row[1], "email": row[2]}

def list_users():
    rows = engine.execute("SELECT id, name, email FROM users").fetchall()
    return [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
