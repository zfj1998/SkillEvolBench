from __future__ import annotations
import re

EXPLICIT_PATTERNS = ["i will", "i'll", "please", "by monday", "by tuesday", "by wednesday", "by friday", "due"]

def extract_actions(messages: list[dict], context: dict) -> list[dict]:
    actions = []
    for msg in messages:
        text = msg.get("text", "").lower()
        if any(pattern in text for pattern in EXPLICIT_PATTERNS) or "?" in text:
            assignee = "unspecified"
            for handle, user in context.get("users_by_name", {}).items():
                if user["slack_id"].lower() in text or handle in text:
                    assignee = handle
                    break
            deadline = None
            if "monday" in text:
                deadline = context.get("default_next_monday")
            elif "friday" in text:
                deadline = context.get("default_next_friday")
            actions.append({
                "id": f"action_{msg['id']}",
                "source_message_id": msg["id"],
                "description": msg.get("text", "")[:120],
                "assignee": assignee,
                "deadline": deadline,
                "status": "open",
                "confidence": 0.6,
                "implicit": False,
                "reason": "Starter matched explicit words or a question mark.",
            })
    return actions

def update_status(actions: list[dict], messages: list[dict], context: dict) -> list[dict]:
    # Starter never compares last-week and this-week evidence or current_date.
    return actions
