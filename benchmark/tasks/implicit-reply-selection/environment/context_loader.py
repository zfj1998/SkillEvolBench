from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def load_messages() -> list[dict]:
    for path in [ROOT / "mail" / "thread.json", ROOT / "mail" / "inbox.json"]:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("messages", [])
    raise FileNotFoundError("No mail/thread.json or mail/inbox.json found")

def load_context() -> dict:
    context = {
        "task_config": read_json(ROOT / "task_config.json", {}),
        "project_state": read_json(ROOT / "context" / "project_state.json", {}),
        "stakeholders": read_json(ROOT / "context" / "stakeholders.json", {}),
        "availability": read_json(ROOT / "calendar" / "availability.json", {}),
    }
    for name in ["thread_notes.md", "api_docs.md", "policy.md"]:
        path = ROOT / "context" / name
        if path.exists():
            context[name] = path.read_text(encoding="utf-8")
    return context
