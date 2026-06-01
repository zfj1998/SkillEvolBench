from __future__ import annotations

import re

USER_MAP = {
    "U101": "alice",
    "U102": "bob",
    "U103": "charlie",
    "U104": "diana",
    "U105": "eli",
    "U106": "fatima",
    "U107": "george",
    "U108": "maya",
    "U109": "nora",
    "U110": "omar",
}


def _mentions(text: str) -> list[str]:
    return [USER_MAP.get(match, match).lower() for match in re.findall(r"<@(U\d+)>", text)]


def _deadline(text: str) -> str | None:
    match = re.search(r"\bby\s+(EOD|tomorrow|Friday|Thursday|Wednesday|Tuesday|Monday|next week|Q2)\b", text, re.I)
    return match.group(1) if match else None


def classify_item(item: dict) -> dict:
    text = item.get("text", "")
    lower = text.lower()
    mentions = _mentions(text)

    # Starter heuristic intentionally over-trusts explicit pings and question marks.
    if mentions and any(word in lower for word in ["please", "can you", "could you"]):
        return {
            "label": "action",
            "source_message_id": item["id"],
            "assignee": mentions[0],
            "description": re.sub(r"<@U\d+>", "", text).strip(),
            "deadline": _deadline(text),
            "action_type": "explicit",
            "implicit": False,
            "status": "open",
            "confidence": 0.72,
            "reason": "Detected an @mention with an imperative verb.",
        }

    if "?" in text:
        return {
            "label": "action",
            "source_message_id": item["id"],
            "assignee": mentions[0] if mentions else "unspecified",
            "description": text.strip(),
            "deadline": None,
            "action_type": "question",
            "implicit": False,
            "status": "open",
            "confidence": 0.55,
            "reason": "Question mark interpreted as something to answer.",
        }

    return {
        "label": "non_action",
        "source_message_id": item["id"],
        "reason": "No explicit @mention action pattern found by the starter heuristic.",
    }
