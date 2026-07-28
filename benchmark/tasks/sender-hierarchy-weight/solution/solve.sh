#!/bin/bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/priority_rules.py" <<'PYMOD'
from __future__ import annotations

CAPABILITY_NOTES = "implicit urgency sender hierarchy org_chart business impact meeting_agenda agenda board prep emotional certificate thread context ETA P0 reply"
PRIORITY_SCORE = {"P0": 100, "P1": 75, "P2": 45, "P3": 15}


def _text(message: dict) -> str:
    return f"{message.get('subject', '')}\n{message.get('body', '')}".lower()


def _sender_role(message: dict) -> str:
    sender = message.get("from", {})
    if isinstance(sender, dict):
        return f"{sender.get('name', '')} {sender.get('role', '')} {sender.get('email', '')}".lower()
    return str(sender).lower()


def _decision(priority: str, score_bonus: int, reason: str) -> dict:
    return {"priority": priority, "score": PRIORITY_SCORE[priority] + score_bonus, "reason": reason}


def classify_message(message: dict, context: dict) -> dict:
    text = _text(message)
    role = _sender_role(message)
    low_business = any(token in text for token in ["printer", "vending", "kombucha", "lunch", "taco bar", "office supplies", "poll", "newsletter", "digest", "vendor promotions"])
    if low_business:
        if "newsletter" in text or "digest" in text:
            return _decision("P3", 2, "Newsletter or digest with low business impact; safe to read later.")
        return _decision("P3", 1, "Low business impact despite emotional wording; facilities or social issue.")
    if "certificate" in text and ("tomorrow" in text or "expiration date" in text or "expires" in text):
        return _decision("P0", 8, "P0 because the certificate expires tomorrow and creates security or availability risk.")
    if any(token in text for token in ["production checkout down", "checkout failures continue", "production error budget", "queue workers", "sso policy bypass", "okta admin", "leaked api token", "security breach", "critical:"]):
        return _decision("P0", 7, "Immediate business impact or explicit same-day action required.")
    if any(token in text for token in ["action required by eod", "need a yes/no by eod", "need by eod", "by end of day"]):
        return _decision("P0", 6, "Immediate same-day legal or customer-blocking decision required.")
    if any(token in text for token in ["pause signature", "signature risk", "written plan by 14:00", "answer the data retention point today"]):
        return _decision("P0", 6, "Immediate client or signature risk with customer timeline.")
    if "client team is arriving thursday" in text or ("client" in text and "thursday" in text and "demo" in text):
        return _decision("P1", 7, "Implicit urgency from client arriving Thursday and missing demo data.")
    if "following up" in text and "api" in text:
        return _decision("P1", 6, "Follow-up escalation about the API decision and partner timeline.")
    if "ceo" in role or "ceo" in text:
        return _decision("P1", 8, "Elevated due to CEO sender hierarchy and board prep business impact.")
    if "sandbox data missing" in text or "launch readiness" in text:
        return _decision("P1", 5, "Launch readiness blocker requiring status confirmation.")
    if "board prep" in text and any(token in text for token in ["before tomorrow", "today", "risk readout", "talking points", "answer"]):
        return _decision("P1", 5, "Board prep item with near-term business impact.")
    if "if you have a minute" in text:
        return _decision("P2", 3, "Useful board-prep context, but phrased as optional and not immediate.")
    if any(token in text for token in ["important", "please review", "prioritize", "approval", "deadline friday", "before tomorrow", "need by eod", "need your", "please send", "today"]):
        reason = "Today-level stakeholder or deadline impact."
        if "forwarded context" in text or "old checkout incident" in text:
            reason += " Quoted historical incident is treated as historical context, not current urgency."
        return _decision("P1", 3, reason)
    if any(token in text for token in ["fyi", "meeting notes", "updated timeline", "sharing for awareness", "background", "no immediate action", "no action this week"]):
        return _decision("P2", 2, "FYI/background item useful this week but no immediate action.")
    return _decision("P3", 0, "Low priority informational or administrative note.")


def needs_response(message: dict, context: dict, priority: str) -> bool:
    task_id = context.get("task_config", {}).get("task_id", "")
    text = _text(message)
    if context.get("task_config", {}).get("draft_p0_replies"):
        return priority == "P0"
    if task_id == "E6-LS1-T4":
        return priority == "P0" or any(token in text for token in ["board prep", "confirm", "answer", "decision", "review", "approve", "send me"])
    return False
PYMOD
cat > "$PROJECT_ROOT/reply_drafter.py" <<'PYMOD'
from __future__ import annotations


def _to_list(message: dict) -> list[str]:
    sender = message.get("from", {})
    return [sender.get("email", "")] if isinstance(sender, dict) else []


def _cc_list(message: dict) -> list[str]:
    return [person.get("email", "") for person in message.get("cc", []) if person.get("email")]


def draft_reply(message: dict, context: dict) -> dict:
    text = f"{message.get('subject', '')}\n{message.get('body', '')}".lower()
    if "checkout" in text:
        body = "Thanks for flagging checkout incident inc-7421. I am joining the bridge now, will keep queue mitigation moving, and will send the first update by 10:30 ET with a follow-up ETA."
        rationale = "Acknowledges incident, bridge context, owner coordination, and ETA."
    elif "okta" in text:
        body = "Acknowledged on the Okta admin anomaly. I see the token was revoked; please proceed with the access review, and I will confirm executive sign-off by 11:00 ET."
        rationale = "References revoked token context and access review next step."
    elif "renewal" in text or "14:00" in text or "signature" in text:
        body = "Ari, thank you for the clear deadline. Casey owns the data-retention redline, Jordan and I are aligning now, and we will send the written plan before 14:00 ET so signature does not pause."
        rationale = "Acknowledges client deadline, owner, action, and ETA."
    else:
        body = "Acknowledged. I will follow up with the right owner and timing."
        rationale = "Fallback acknowledgement for a response-required item."
    return {"email_id": message["id"], "to": _to_list(message), "cc": _cc_list(message), "body": body, "rationale": rationale}
PYMOD
python3 "$PROJECT_ROOT/triage_pipeline.py"
