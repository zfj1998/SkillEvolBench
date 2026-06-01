"""Integration tests - exercises cross-feature interactions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import sqlite3
from src.app import setup_database
from src.notifications import send_notification
from src.search import search_events, get_event_types
from src.export import export_events


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    setup_database(conn)
    conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    conn.commit()
    yield conn
    conn.close()


def test_notify_then_search(db):
    """Send notification, then search for it."""
    send_notification(db, 1, "login", "User logged in")
    send_notification(db, 1, "purchase", "Bought premium plan")

    # Search by description
    results = search_events(db, "logged")
    assert len(results) == 1

    # Search by type - THIS WILL FAIL if column names don't match
    results = search_events(db, "", event_type="login")
    assert len(results) == 1


def test_notify_then_export(db):
    """Send notifications, then export them."""
    send_notification(db, 1, "login", "User logged in")
    csv_data = export_events(db, user_id=1)
    assert "logged in" in csv_data


def test_full_workflow(db):
    """Full workflow: notify -> search -> export."""
    send_notification(db, 1, "signup", "New user signed up")
    send_notification(db, 1, "purchase", "Bought item")

    # Search
    results = search_events(db, "signed up")
    assert len(results) == 1

    # Get types
    types = get_event_types(db)
    assert len(types) == 2

    # Export
    csv_data = export_events(db)
    assert "signup" in csv_data or "signed up" in csv_data
