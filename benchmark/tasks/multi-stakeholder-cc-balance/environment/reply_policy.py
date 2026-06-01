from __future__ import annotations

def select_actions(messages: list[dict], context: dict) -> list[dict]:
    actions = []
    for message in messages:
        text = f"{message.get('subject', '')}\n{message.get('body', '')}".lower()
        if "newsletter" in text or "automated" in text:
            actions.append({"email_id": message["id"], "action": "ignore", "reason": "Low-value broadcast."})
        elif "?" in text or "can you" in text or "would you" in text:
            actions.append({"email_id": message["id"], "action": "reply", "reason": "Detected a direct question or request."})
        else:
            actions.append({"email_id": message["id"], "action": "acknowledge", "reason": "No question, but safe to acknowledge."})
    return actions

def draft_reply(message: dict, context: dict) -> dict:
    cc = [person["email"] for person in message.get("cc", [])]
    return {
        "email_id": message["id"],
        "to": [message["from"]["email"]],
        "cc": cc,
        "body": "Thanks for the note. This sounds good to me; I will check on the details and follow up soon.",
        "rationale": "Starter reply only uses the latest message and a generic agreeable tone.",
    }
