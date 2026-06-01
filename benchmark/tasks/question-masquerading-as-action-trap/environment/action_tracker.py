from __future__ import annotations
import json
from pathlib import Path

import extractor_policy
import followup_drafter
from context_loader import load_context, load_messages

ROOT = Path(__file__).resolve().parent

def main() -> None:
    messages = load_messages()
    context = load_context()
    actions = extractor_policy.extract_actions(messages, context)
    actions = extractor_policy.update_status(actions, messages, context)
    followups = followup_drafter.draft_followups(actions, context)
    summary = {
        "total_actions": len(actions),
        "open": sum(1 for action in actions if action.get("status") == "open"),
        "completed": sum(1 for action in actions if action.get("status") == "completed"),
        "delayed": sum(1 for action in actions if action.get("status") == "delayed"),
        "overdue": sum(1 for action in actions if action.get("status") == "overdue"),
        "no_update": sum(1 for action in actions if action.get("status") == "no_update"),
    }
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "actions.json").write_text(json.dumps({"actions": actions, "followups": followups, "summary": summary}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
