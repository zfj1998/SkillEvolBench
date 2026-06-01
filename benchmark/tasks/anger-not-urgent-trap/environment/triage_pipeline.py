from __future__ import annotations
import json
from pathlib import Path

import priority_rules
import reply_drafter
from context_loader import load_context

ROOT = Path(__file__).resolve().parent

def main() -> None:
    mailbox = json.loads((ROOT / "mail" / "messages.json").read_text(encoding="utf-8"))
    messages = mailbox["messages"]
    context = load_context()
    classified = []
    for message in messages:
        decision = priority_rules.classify_message(message, context)
        item = {
            "id": message["id"],
            "thread_id": message["thread_id"],
            "subject": message["subject"],
            "sender": message["from"]["email"],
            "priority": decision["priority"],
            "score": decision.get("score", 0),
            "reason": decision.get("reason", ""),
            "needs_response": priority_rules.needs_response(message, context, decision["priority"]),
        }
        classified.append(item)
    classified.sort(key=lambda item: ({"P0": 0, "P1": 1, "P2": 2, "P3": 3}[item["priority"]], -item["score"], item["id"]))
    for rank, item in enumerate(classified, start=1):
        item["rank"] = rank
    response_ids = [item["id"] for item in classified if item["needs_response"]]
    by_id = {message["id"]: message for message in messages}
    drafts = []
    if context.get("task_config", {}).get("draft_p0_replies"):
        drafts = [reply_drafter.draft_reply(by_id[item["id"]], context) for item in classified if item["priority"] == "P0" and item["needs_response"]]
    output = {
        "items": classified,
        "response_list": response_ids,
        "drafts": drafts,
        "summary": {
            "total": len(messages),
            "counts": {priority: sum(1 for item in classified if item["priority"] == priority) for priority in ["P0", "P1", "P2", "P3"]},
        },
    }
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "triage.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
