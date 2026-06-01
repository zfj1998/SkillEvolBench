"""Notification tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import sqlite3
from src.notifications import setup_notifications_table, send_notification, get_user_notifications


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    setup_notifications_table(conn)
    conn.commit()
    yield conn
    conn.close()


def test_send_notification(db):
    result = send_notification(db, 1, "login", "User logged in")
    assert result is True


def test_get_notifications(db):
    send_notification(db, 1, "login", "Logged in")
    send_notification(db, 1, "purchase", "Bought item")
    notifs = get_user_notifications(db, 1)
    assert len(notifs) == 2
