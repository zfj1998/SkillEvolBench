from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def load_context() -> dict:
    context = {
        "sender_directory": read_json(ROOT / "contacts" / "sender_directory.json", {}),
        "org_chart": read_json(ROOT / "contacts" / "org_chart.json", {}),
        "calendar": read_json(ROOT / "calendar" / "today.json", {}),
        "task_config": read_json(ROOT / "task_config.json", {}),
    }
    agenda_path = ROOT / "calendar" / "meeting_agenda.md"
    if agenda_path.exists():
        context["meeting_agenda"] = agenda_path.read_text(encoding="utf-8")
    thread_path = ROOT / "mail" / "thread_context.md"
    if thread_path.exists():
        context["thread_context"] = thread_path.read_text(encoding="utf-8")
    return context
