#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path
import re

path = Path("database.py")
text = path.read_text(encoding="utf-8")

text = re.sub(
    r"<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> security/fix-sql-injection",
    lambda m: m.group(1) if "search_users" in m.group(1) else m.group(2),
    text,
    flags=re.S,
)
text = text.replace(
    'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
    'cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
)
text = text.replace(
    """cursor.execute(f"SELECT * FROM users WHERE name LIKE '%{query}%'")""",
    'cursor.execute("SELECT * FROM users WHERE name LIKE ?", (f"%{query}%",))',
)
text = text.replace(
    """cursor.execute(f"INSERT INTO users (name, email) VALUES ('{name}', '{email}')")""",
    'cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))',
)
path.write_text(text, encoding="utf-8")
PY
