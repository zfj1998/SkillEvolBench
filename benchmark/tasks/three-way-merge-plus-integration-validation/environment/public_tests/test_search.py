"""Search feature tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import sqlite3


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE user_events (
        id INTEGER PRIMARY KEY, user_id INTEGER,
        type TEXT, description TEXT, created_at TIMESTAMP)""")
    conn.execute("INSERT INTO user_events (user_id, type, description) VALUES (1, 'login', 'User logged in')")
    conn.execute("INSERT INTO user_events (user_id, type, description) VALUES (1, 'purchase', 'Bought item')")
    conn.commit()
    yield conn
    conn.close()


def test_search_events(db):
    from src.search import search_events
    results = search_events(db, "logged")
    assert len(results) == 1


def test_search_by_type(db):
    from src.search import search_events
    results = search_events(db, "", event_type="login")
    assert len(results) == 1


def test_get_event_types(db):
    from src.search import get_event_types
    types = get_event_types(db)
    assert len(types) == 2
