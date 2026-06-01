from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_items() -> list[dict]:
    slack_path = ROOT / "slack" / "channel_export.json"
    if slack_path.exists():
        payload = json.loads(slack_path.read_text(encoding="utf-8"))
        return [
            {
                "id": msg["id"],
                "text": msg.get("text", ""),
                "speaker": msg.get("user_name", ""),
                "timestamp": msg.get("ts", ""),
                "kind": "slack_message",
            }
            for msg in payload.get("messages", [])
        ]

    meeting_path = ROOT / "meeting" / "paragraphs.json"
    if meeting_path.exists():
        payload = json.loads(meeting_path.read_text(encoding="utf-8"))
        return [
            {
                "id": item["id"],
                "text": item.get("text", ""),
                "speaker": item.get("speaker", ""),
                "timestamp": item.get("timestamp", ""),
                "kind": "meeting_paragraph",
            }
            for item in payload.get("paragraphs", [])
        ]

    return []
