from __future__ import annotations


def status_summary(actions: list[dict]) -> dict:
    summary = {"open": 0, "completed": 0, "blocked": 0, "follow_up_needed": 0}
    for action in actions:
        status = action.get("status", "open")
        summary[status] = summary.get(status, 0) + 1
    return summary


def build_summary(actions: list[dict], non_actions: list[dict], items: list[dict]) -> dict:
    return {
        "key_decisions": [],
        "follow_up_needed": [a.get("source_message_id") for a in actions if a.get("status") == "follow_up_needed"],
        "notes": "Starter summary only counts extracted actions and does not synthesize decisions.",
    }
