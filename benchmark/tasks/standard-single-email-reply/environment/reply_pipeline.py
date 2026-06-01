from __future__ import annotations
import json
from pathlib import Path

import reply_policy
from context_loader import load_context, load_messages

ROOT = Path(__file__).resolve().parent

def main() -> None:
    messages = load_messages()
    context = load_context()
    by_id = {message["id"]: message for message in messages}
    actions = reply_policy.select_actions(messages, context)
    replies = []
    acknowledgements = []
    ignored = []
    for action in actions:
        message = by_id[action["email_id"]]
        if action["action"] == "reply":
            replies.append(reply_policy.draft_reply(message, context))
        elif action["action"] == "acknowledge":
            ack = reply_policy.draft_reply(message, context)
            ack["body"] = ack["body"] if len(ack["body"]) < 140 else "Thanks, acknowledged."
            acknowledgements.append(ack)
        else:
            ignored.append({"email_id": message["id"], "reason": action.get("reason", "")})
    output = {"actions": actions, "replies": replies, "acknowledgements": acknowledgements, "ignored": ignored}
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "replies.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
