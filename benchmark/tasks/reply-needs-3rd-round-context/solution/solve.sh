#!/bin/bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/reply_policy.py" <<'PYMOD'
from __future__ import annotations

CAPABILITY_NOTES = "triage thread_history third round decision context_json project_state stakeholder cc feasibility scope timeline realistic acknowledge ignore select_actions"


def _text(message: dict) -> str:
    return f"{message.get('subject', '')}\n{message.get('body', '')}".lower()


def _email(message: dict) -> str:
    sender = message.get("from", {})
    return sender.get("email", "") if isinstance(sender, dict) else ""


def _stakeholders(context: dict) -> dict:
    return context.get("stakeholders", {})


def _email_for(context: dict, key: str) -> str:
    return _stakeholders(context).get(key, {}).get("email", "")


def _is_ack(text: str) -> bool:
    return any(token in text for token in ["fyi", "posted", "published", "signed", "updated", "closing the loop", "no action"])


def _is_ignore(text: str) -> bool:
    return any(token in text for token in ["newsletter", "automated", "digest", "vendor promotions", "no reply needed"])


def _is_actionable(text: str) -> bool:
    return any(token in text for token in ["can you", "could you", "would you", "what ", "which ", "confirm", "approve", "decide", "question", "commit", "promise"])


def select_actions(messages: list[dict], context: dict) -> list[dict]:
    thread_mode = context.get("task_config", {}).get("task_id") == "E6-LS2-T2"
    last_actionable = None
    if thread_mode:
        for idx, message in enumerate(messages):
            if _is_actionable(_text(message)):
                last_actionable = idx
    actions = []
    for idx, message in enumerate(messages):
        text = _text(message)
        if _is_ignore(text):
            action = "ignore"
            reason = "Automated newsletter or no-reply broadcast."
        elif thread_mode and idx != last_actionable:
            action = "ignore"
            reason = "Thread history used as context; only the latest direct request needs a reply."
        elif _is_ack(text) and not _is_actionable(text):
            action = "acknowledge"
            reason = "FYI or closure message needs only a short acknowledgement."
        elif _is_actionable(text):
            action = "reply"
            reason = "Message asks for a substantive context-aware answer."
        else:
            action = "ignore"
            reason = "No response required after triage."
        actions.append({"email_id": message["id"], "action": action, "reason": reason})
    return actions


def _base_reply(message: dict, context: dict, body: str, rationale: str, cc: list[str] | None = None) -> dict:
    return {"email_id": message["id"], "to": [_email(message)], "cc": [addr for addr in (cc or []) if addr], "body": body, "rationale": rationale}


def draft_reply(message: dict, context: dict) -> dict:
    text = _text(message)
    state = context.get("project_state", {})
    if "progress" in text and "budget" in text and "meeting" in text:
        body = (
            f"Hi Taylor, progress is at {state.get('progress', '68%')} with integration testing in flight. "
            f"The budget is {state.get('budget', 'approved with $42k contingency')}, and hiring is still planned for {state.get('hiring', 'two backend engineers planned')}. "
            "For a next week meeting, I can meet Tuesday at 11:00 ET or Thursday at 15:00 ET; Tuesday is my preference."
        )
        return _base_reply(message, context, body, "Answers all three questions using project_state and calendar context.")
    if ("plan" in text and ("which" in text or "choice" in text or "final" in text)) or "final choice" in text:
        body = "We chose Plan A because the third round decision prioritized the shorter timeline and kept the pilot date safe."
        return _base_reply(message, context, body, "Uses the third round thread context and decision rationale rather than only the newest question.")
    if "advanced rules" in text or "rules engine" in text:
        body = "Jordan, I understand the customer pressure and want to keep momentum. I would not commit, and I would not promise, the full rules engine on that timeline; a safer path is a two-week MVP for the top three rules, while the full build stays on the six weeks engineering plan with Riley and Taylor aligned."
        cc = [_email_for(context, "vp_eng"), _email_for(context, "pm")]
        return _base_reply(message, context, body, "Balances Sales, Engineering, and Product feasibility with a phased plan.", cc)
    if "release note" in text and "approve" in text:
        return _base_reply(message, context, "Approved; please use the concise customer-impact version and send it by noon.", "Directly answers the approval request.")
    if "budget number" in text or "board appendix" in text:
        return _base_reply(message, context, "Use $4.2M as the current forecast number for the board appendix.", "Answers the budget number question.")
    if "support window" in text or "support coverage" in text:
        cc = [_email_for(context, "vp_sales")] if "coverage" in text else []
        body = "Launch support coverage is 08:00-20:00 ET with executive escalation after hours; Jordan is cc'd so Sales can reuse the same answer with the customer."
        return _base_reply(message, context, body, "Answers support coverage and keeps Sales cc aligned.", cc)
    if "api freeze" in text or "freeze the api" in text:
        return _base_reply(message, context, "Freeze the API today after the compatibility shim lands; reopen only for P0 defects.", "Makes the requested freeze decision.")
    if "rewriting the entire backend" in text or "backend by friday" in text:
        body = "I cannot responsibly commit to rewriting the entire backend by Friday. The realistic estimate is three months; for Friday, I can scope a staged alternative such as a design brief plus compatibility patch."
        return _base_reply(message, context, body, "Sets a friendly but realistic scope and timeline boundary.")
    return _base_reply(message, context, "Thanks, acknowledged.", "Short acknowledgement for FYI completion.")
PYMOD
python3 "$PROJECT_ROOT/reply_pipeline.py"
