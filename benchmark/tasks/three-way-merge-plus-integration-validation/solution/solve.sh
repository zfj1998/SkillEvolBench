#!/bin/bash
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

# Resolve app.py - keep notifications setup
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('src/app.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Main application."""\nimport sqlite3\n\ndef get_db(db_path=":memory:"):\n    conn = sqlite3.connect(db_path)\n    conn.row_factory = sqlite3.Row\n    return conn\n\ndef setup_database(db):\n    db.execute("""\n        CREATE TABLE IF NOT EXISTS users (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            name TEXT NOT NULL,\n            email TEXT NOT NULL UNIQUE\n        )\n    """)\n    from src.notifications import setup_notifications_table\n    setup_notifications_table(db)\n    db.commit()\n', encoding='utf-8')
PYWRITE_1

# Resolve export.py - keep json format + use 'type' column
python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('src/export.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Data export feature."""\nimport csv\nimport io\nimport json\n\ndef export_users(db, format="csv"):\n    users = db.execute("SELECT * FROM users").fetchall()\n    if format == "csv":\n        output = io.StringIO()\n        writer = csv.writer(output)\n        writer.writerow(["id", "name", "email"])\n        for user in users:\n            writer.writerow([user["id"], user["name"], user["email"]])\n        return output.getvalue()\n    elif format == "json":\n        return json.dumps([dict(u) for u in users])\n    return str([dict(u) for u in users])\n\ndef export_events(db, user_id=None):\n    if user_id:\n        events = db.execute("SELECT * FROM user_events WHERE user_id = ?", (user_id,)).fetchall()\n    else:\n        events = db.execute("SELECT * FROM user_events").fetchall()\n    output = io.StringIO()\n    writer = csv.writer(output)\n    writer.writerow(["id", "user_id", "type", "description", "created_at"])\n    for event in events:\n        writer.writerow([event["id"], event["user_id"], event["type"],\n                         event["description"], event["created_at"]])\n    return output.getvalue()\n', encoding='utf-8')
PYWRITE_2

# Fix search.py - use 'type' column (match notifications)
python3 - <<'PYWRITE_3'
from pathlib import Path
target = Path('src/search.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Search feature - column names unified with notifications."""\n\ndef search_events(db, query, event_type=None):\n    sql = "SELECT * FROM user_events WHERE description LIKE ?"\n    params = [f"%{query}%"]\n    if event_type:\n        sql += " AND type = ?"\n        params.append(event_type)\n    return db.execute(sql, params).fetchall()\n\ndef get_event_types(db):\n    return db.execute("SELECT DISTINCT type FROM user_events").fetchall()\n', encoding='utf-8')
PYWRITE_3

echo "Resolved: all conflicts + unified column name to 'type'"
