"""Notification system - from feat/notifications branch."""


def setup_notifications_table(db):
    """Create user_events table for notifications."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def send_notification(db, user_id, event_type, description):
    """Record a notification event."""
    db.execute(
        "INSERT INTO user_events (user_id, type, description) VALUES (?, ?, ?)",
        (user_id, event_type, description)
    )
    db.commit()
    return True


def get_user_notifications(db, user_id):
    """Get notifications for a user."""
    return db.execute(
        "SELECT * FROM user_events WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
