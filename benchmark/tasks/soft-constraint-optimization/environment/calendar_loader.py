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
        "participants": read_json(ROOT / "calendar" / "participants.json", {"participants": []}).get("participants", []),
        "request": read_json(ROOT / "scheduling_request.json", {}),
        "preferences": read_json(ROOT / "preferences.json", {}),
        "team": read_json(ROOT / "team.json", {}),
        "last_meeting": read_json(ROOT / "last_meeting.json", {}),
    }
    request_md = ROOT / "scheduling_request.md"
    if request_md.exists():
        context["request_md"] = request_md.read_text(encoding="utf-8")
    return context
