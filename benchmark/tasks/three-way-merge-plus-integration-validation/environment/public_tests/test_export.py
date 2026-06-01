"""Export feature tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import sqlite3
from src.notifications import setup_notifications_table


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    setup_notifications_table(conn)
    conn.commit()
    yield conn
    conn.close()


def test_export_users_csv(db):
    from src.export import export_users
    csv_data = export_users(db, format="csv")
    assert "Alice" in csv_data


def test_export_users_json(db):
    from src.export import export_users
    json_data = export_users(db, format="json")
    assert "Alice" in json_data
