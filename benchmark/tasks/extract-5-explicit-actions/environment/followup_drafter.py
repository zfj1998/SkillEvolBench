from __future__ import annotations

def draft_followups(actions: list[dict], context: dict) -> list[dict]:
    drafts = []
    for action in actions:
        if action.get("status") == "overdue":
            drafts.append({
                "action_id": action["id"],
                "to": action.get("assignee", "unspecified"),
                "body": "This is overdue. Please send an update.",
                "tone": "blunt",
            })
    return drafts
