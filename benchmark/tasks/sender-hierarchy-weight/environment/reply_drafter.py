from __future__ import annotations

def draft_reply(message: dict, context: dict) -> dict:
    return {
        "email_id": message["id"],
        "to": [message["from"]["email"]],
        "cc": [person["email"] for person in message.get("cc", [])],
        "body": "Thanks for flagging this. I am looking into it and will follow up soon.",
        "rationale": "Generic acknowledgement generated from the latest message only.",
    }
