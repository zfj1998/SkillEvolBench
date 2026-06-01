"""Search feature - from feat/search branch."""


def search_events(db, query, event_type=None):
    """Search user events."""
    sql = "SELECT * FROM user_events WHERE description LIKE ?"
    params = [f"%{query}%"]

    if event_type:
        sql += " AND event_type = ?"  # BUG: column is actually 'type' in notifications
        params.append(event_type)

    return db.execute(sql, params).fetchall()


def get_event_types(db):
    """Get distinct event types."""
    return db.execute("SELECT DISTINCT event_type FROM user_events").fetchall()
