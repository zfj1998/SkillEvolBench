from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def load_messages() -> list[dict]:
    payload = read_json(ROOT / "slack" / "channel_export.json", {"messages": []})
    return payload.get("messages", [])

def load_context() -> dict:
    users = read_json(ROOT / "slack" / "users.json", {})
    users_by_name = {
        key: {"slack_id": value["id"], "email": value["email"], "timezone": value["timezone"], "role": value["role"]}
        for key, value in users.items()
    }
    context = {
        "users_by_name": users_by_name,
        "current_date": read_json(ROOT / "context" / "current_date.json", {"date": "2026-04-23"}).get("date"),
        "default_next_monday": "2026-04-27",
        "default_next_friday": "2026-04-24",
        "task_config": read_json(ROOT / "task_config.json", {}),
    }
    for name in ["last_week_thread.md", "this_week_thread.md", "standup_template.md"]:
        path = ROOT / "context" / name
        if path.exists():
            context[name] = path.read_text(encoding="utf-8")
    return context
