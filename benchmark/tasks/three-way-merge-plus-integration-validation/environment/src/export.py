"""Data export feature - from feat/export branch."""
<<<<<<< HEAD
import csv
import io


def export_users(db, format="csv"):
    """Export user data."""
    users = db.execute("SELECT * FROM users").fetchall()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "email"])
        for user in users:
            writer.writerow([user["id"], user["name"], user["email"]])
        return output.getvalue()
    return str([dict(u) for u in users])
=======
import csv
import io
import json


def export_users(db, format="csv"):
    """Export user data."""
    users = db.execute("SELECT * FROM users").fetchall()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "email"])
        for user in users:
            writer.writerow([user["id"], user["name"], user["email"]])
        return output.getvalue()
    elif format == "json":
        return json.dumps([dict(u) for u in users])
    return str([dict(u) for u in users])
>>>>>>> feat/notifications


def export_events(db, user_id=None):
    """Export events data."""
<<<<<<< HEAD
    if user_id:
        events = db.execute("SELECT * FROM user_events WHERE user_id = ?", (user_id,)).fetchall()
    else:
        events = db.execute("SELECT * FROM user_events").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "event_type", "description", "created_at"])
    for event in events:
        writer.writerow([event["id"], event["user_id"], event["event_type"],
                         event["description"], event["created_at"]])
    return output.getvalue()
=======
    if user_id:
        events = db.execute("SELECT * FROM user_events WHERE user_id = ?", (user_id,)).fetchall()
    else:
        events = db.execute("SELECT * FROM user_events").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "type", "description", "created_at"])
    for event in events:
        writer.writerow([event["id"], event["user_id"], event["type"],
                         event["description"], event["created_at"]])
    return output.getvalue()
>>>>>>> feat/notifications
