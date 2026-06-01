from __future__ import annotations

KEYWORD_PRIORITY = [
    ("P0", ["urgent", "critical", "asap", "production down", "breach", "eod", "!!!"]),
    ("P1", ["important", "deadline", "please review", "prioritize", "approval"]),
    ("P2", ["fyi", "notes", "timeline", "update"]),
    ("P3", ["newsletter", "lunch", "office supplies", "poll"]),
]

def classify_message(message: dict, context: dict) -> dict:
    text = f"{message.get('subject', '')}\n{message.get('body', '')}".lower()
    for priority, keywords in KEYWORD_PRIORITY:
        if any(keyword in text for keyword in keywords):
            return {"priority": priority, "score": 100 - ["P0", "P1", "P2", "P3"].index(priority) * 20, "reason": f"Matched visible keyword for {priority}."}
    return {"priority": "P3", "score": 10, "reason": "No explicit urgency keyword found."}

def needs_response(message: dict, context: dict, priority: str) -> bool:
    text = f"{message.get('subject', '')}\n{message.get('body', '')}".lower()
    return priority in {"P0", "P1"} or "?" in text or "please" in text
