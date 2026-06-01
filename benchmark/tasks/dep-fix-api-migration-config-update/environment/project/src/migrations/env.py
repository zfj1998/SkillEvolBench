"""Legacy migration environment."""
from database import engine

def run_migrations():
    engine.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    engine.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER)")
    return {"status": "ok", "revision": "head"}
