"""Outcome verifier for E1-LS5-T6: three-way-merge-plus-integration-validation."""
import sys
import os
import sqlite3
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")
sys.path.insert(0, PROJECT_DIR)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from src.app import setup_database
    setup_database(conn)
    conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    conn.commit()
    yield conn
    conn.close()


class TestHidden:
    def test_h1_no_conflict_markers(self):
        """H1: No conflict markers in any file."""
        for fname in ["src/app.py", "src/export.py"]:
            fpath = os.path.join(PROJECT_DIR, fname)
            with open(fpath) as f:
                content = f.read()
            assert "<<<<<<<" not in content, f"{fname} has conflict markers"
            assert ">>>>>>>" not in content, f"{fname} has conflict markers"

    def test_h2_each_feature_works(self, db):
        """H2: Each feature should work independently."""
        # Notifications
        from src.notifications import send_notification, get_user_notifications
        send_notification(db, 1, "login", "Logged in")
        notifs = get_user_notifications(db, 1)
        assert len(notifs) >= 1, "Notifications feature broken"

        # Search
        from src.search import search_events
        results = search_events(db, "Logged")
        assert len(results) >= 1, "Search feature broken"

        # Export
        from src.export import export_users
        csv_data = export_users(db, format="csv")
        assert "Alice" in csv_data, "Export feature broken"

    def test_h3_integration_test_passes(self, db):
        """H3: Cross-feature integration should work."""
        from src.notifications import send_notification
        from src.search import search_events

        send_notification(db, 1, "login", "User logged in")

        # Search by type should work (column names must be consistent)
        results = search_events(db, "", event_type="login")
        assert len(results) == 1, (
            "Integration failure: search by event type doesn't work. "
            "Column name mismatch between search and notifications?"
        )

    def test_h4_column_names_unified(self, db):
        """H4: search and notifications should use the same column name."""
        with open(os.path.join(PROJECT_DIR, "src", "search.py")) as f:
            search_src = f.read()
        with open(os.path.join(PROJECT_DIR, "src", "notifications.py")) as f:
            notif_src = f.read()

        # notifications creates column named 'type'
        # search should reference 'type' (not 'event_type')
        # OR notifications should create 'event_type'
        # Key: they must be consistent
        notif_uses_type = '"type"' in notif_src or "'type'" in notif_src
        search_uses_type = 'type' in search_src

        if notif_uses_type:
            # If notifications uses 'type', search should NOT use 'event_type'
            assert "event_type" not in search_src, (
                "Column name mismatch: notifications uses 'type' but search uses 'event_type'"
            )
