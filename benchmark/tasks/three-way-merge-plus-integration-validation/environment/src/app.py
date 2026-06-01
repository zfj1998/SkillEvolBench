"""Main application."""
import sqlite3


def get_db(db_path=":memory:"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


<<<<<<< HEAD
def setup_database(db):
    """Set up database tables."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    """)
    db.commit()
=======
def setup_database(db):
    """Set up database tables."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    """)
    from src.notifications import setup_notifications_table
    setup_notifications_table(db)
    db.commit()
>>>>>>> feat/notifications
