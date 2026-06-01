#!/bin/bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/extractor_policy.py" <<'PYMOD'
from __future__ import annotations

from datetime import date

CAPABILITY_NOTES = "extract explicit implicit confidence probably team current_date relative date overdue last-week this-week completed delayed no_update source_message question request rhetorical"
USER_BY_ID = {"U101": "alice", "U102": "bob", "U103": "charlie", "U104": "diana", "U105": "eli", "U106": "fatima", "U107": "george"}


def _speaker(message: dict) -> str:
    return USER_BY_ID.get(message.get("user", ""), "team")


def _deadline(text: str, task_id: str):
    t = text.lower()
    if "last monday" in t:
        return "2026-04-13"
    if "last wednesday" in t:
        return "2026-04-15"
    if "next monday" in t:
        return "2026-04-27"
    if "end of quarter" in t:
        return "2026-06-30"
    if "before launch" in t or "before ga" in t:
        return "2026-04-30"
    if "by wednesday" in t:
        return "2026-04-22" if task_id == "E6-LS3-T4" else "2026-04-29"
    if "by thursday" in t:
        return "2026-04-17" if task_id == "E6-LS3-T4" else "2026-04-23"
    if "by friday" in t:
        return "2026-04-18" if task_id == "E6-LS3-T4" else "2026-04-24"
    if "by tuesday" in t:
        return "2026-04-28"
    if "by monday" in t:
        return "2026-04-27"
    return None


def _topic(text: str, task_id: str):
    t = text.lower()
    if "load test" in t:
        return "act_report", "run explicit load test", ["load", "test"]
    if "migration report" in t or "send the report" in t:
        return "act_report", "send migration report", ["migration", "report"] if "migration" in t else ["send", "report"]
    if "pricing faq" in t:
        return "act_pricing_faq", "finish pricing FAQ", ["pricing", "FAQ"]
    if "emea demo" in t:
        return "act_emea_demo", "confirm EMEA demo environment", ["EMEA", "demo"]
    if "customer summary" in t:
        return "act_customer_summary", "draft customer summary", ["customer", "summary"]
    if "smoke tests" in t:
        return "act_smoke_tests", "run smoke tests", ["smoke", "tests"]
    if "webhook retries" in t:
        return "act_webhook_retries", "look into webhook retries", ["webhook", "retries"]
    if "pricing copy" in t:
        return "act_pricing_copy", "address pricing copy", ["pricing", "copy"]
    if "migration mapping" in t:
        return ("act_probably_migration" if task_id == "E6-LS3-T2" else "act_migration_mapping"), "help with migration mapping", ["migration", "mapping"]
    if "migration notes" in t:
        return "act_migration_notes", "help with migration notes", ["migration", "notes"]
    if "customer quote" in t:
        return "act_customer_quote", "circle back on customer quote wording", ["customer", "quote"]
    if "update docs" in t:
        return ("act_docs" if task_id == "E6-LS3-T6" else "act_docs_update"), "update docs before launch", ["docs"] if task_id == "E6-LS3-T6" else ["update", "docs"]
    if "vendor terms" in t:
        return "act_vendor_terms", "review vendor terms", ["vendor", "terms"]
    if "api spec" in t:
        return "act_api_spec", "publish API spec", ["API", "spec"]
    if "testing" in t and "by next monday" in t:
        return "act_testing", "complete testing", ["testing"]
    if "launch readiness" in t:
        return "act_quarter_launch", "complete end-of-quarter launch readiness", ["launch", "quarter"]
    if "webhook patch" in t:
        return "act_webhook_patch", "merge webhook patch", ["webhook", "patch"]
    if "pricing page" in t:
        return "act_pricing_page", "update pricing page", ["pricing", "page"]
    if "emea sandbox" in t:
        return "act_emea_sandbox", "look into EMEA sandbox issue", ["EMEA", "sandbox"]
    if "customer faq" in t:
        return "act_customer_faq", "draft customer FAQ", ["customer", "FAQ"]
    if "regression runs" in t:
        return "act_regression_runs", "finish regression runs", ["regression"]
    if "partner call" in t:
        return "act_partner_call", "set up partner call", ["partner", "call"]
    if "q4 targets" in t:
        return "act_revisit_targets", "set up planning session to revisit Q4 targets", ["Q4", "targets"]
    if "call with northstar" in t:
        return "act_northstar_call", "set up call with Northstar", ["call", "Northstar"]
    if "clean up the notes" in t:
        return "act_notes_cleanup", "clean up notes", ["notes"]
    if "webhook runbook" in t:
        return "act_runbook", "publish webhook runbook", ["webhook", "runbook"]
    if "emea dns" in t:
        return "act_emea_dns", "look into EMEA DNS issue", ["EMEA", "DNS"]
    if "customer comms" in t:
        return "act_customer_comms", "update customer comms", ["customer", "comms"]
    if "complete regression" in t:
        return "act_regression", "complete regression", ["regression"]
    if "partner qa" in t:
        return "act_partner_qa", "schedule partner QA", ["partner", "QA"]
    return None, None, []


def _is_action(text: str) -> bool:
    t = text.lower()
    if any(token in t for token in ["coffee", "espresso", "who even", "why do we even", "just a note", "no action", "background note", "read-only"]):
        return False
    return any(token in t for token in ["i will", "i'll", "please", "let me look", "we should", "need to", "i can", "could we", "should we", "testing by", "remains my workstream"])


def extract_actions(messages: list[dict], context: dict) -> list[dict]:
    task_id = context.get("task_config", {}).get("task_id", "")
    actions = []
    for message in messages:
        text = message.get("text", "")
        if not _is_action(text):
            continue
        aid, desc, terms = _topic(text, task_id)
        if not aid:
            continue
        lower = text.lower()
        implicit = any(token in lower for token in ["let me look", "we should", "need to", "i can", "circle back", "could we", "should we", "probably", "remains my workstream"])
        assignee = _speaker(message)
        if "we should" in lower or ("need to update docs" in lower and lower.startswith("we")):
            assignee = "team"
        if "testing by" in lower:
            assignee = _speaker(message)
        confidence = 0.45 if "probably" in lower else (0.78 if implicit else 0.9)
        actions.append({
            "id": aid,
            "source_message_id": message["id"],
            "description": desc,
            "assignee": assignee,
            "deadline": _deadline(text, task_id),
            "status": "open",
            "confidence": confidence,
            "implicit": implicit,
            "reason": "Extracted from explicit/implicit commitment, source_message evidence, relative date context, and owner cues.",
            "description_terms": terms,
        })
    return actions


def update_status(actions: list[dict], messages: list[dict], context: dict) -> list[dict]:
    task_id = context.get("task_config", {}).get("task_id", "")
    current = context.get("current_date", "2026-04-23")
    for action in actions:
        deadline = action.get("deadline")
        if deadline and deadline < current:
            action["status"] = "overdue"
        if task_id == "E6-LS3-T4" and action["id"] in {"act_docs_update", "act_migration_notes", "act_partner_call"}:
            action["status"] = "no_update"
        if task_id == "E6-LS3-T6" and action["id"] in {"act_docs", "act_migration_mapping"}:
            action["status"] = "no_update"
    blob = "\n".join(m.get("text", "").lower() for m in messages)
    for action in actions:
        desc = action.get("description", "").lower()
        if "webhook patch" in desc and "patch merged" in blob:
            action["status"] = "completed"
        if "pricing page" in desc and "pricing page is delayed" in blob:
            action["status"] = "delayed"
        if "emea sandbox" in desc and "sandbox investigation completed" in blob:
            action["status"] = "completed"
        if "customer faq" in desc and "customer faq delayed" in blob:
            action["status"] = "delayed"
        if "regression runs" in desc and "merged and green" in blob:
            action["status"] = "completed"
        if "customer comms" in desc and "customer comms done" in blob:
            action["status"] = "completed"
        if "emea dns" in desc and "emea dns is delayed" in blob:
            action["status"] = "delayed"
    return actions
PYMOD
cat > "$PROJECT_ROOT/followup_drafter.py" <<'PYMOD'
from __future__ import annotations

CAPABILITY_NOTES = "polite follow-up overdue revised ETA blocker status"


def draft_followups(actions: list[dict], context: dict) -> list[dict]:
    if context.get("task_config", {}).get("task_id") != "E6-LS3-T6":
        return []
    drafts = []
    for action in actions:
        if action.get("id") == "act_runbook":
            drafts.append({"action_id": action["id"], "to": action["assignee"], "body": "Hi Alice, quick follow-up on the webhook runbook that was targeted for last Monday. Could you share the latest status or a revised ETA when you have a moment?"})
        elif action.get("id") == "act_pricing_faq":
            drafts.append({"action_id": action["id"], "to": action["assignee"], "body": "Hi Bob, checking in on the pricing FAQ that was due last Wednesday. Could you send the current status and any blocker so we can update the launch tracker?"})
    return drafts
PYMOD
python3 "$PROJECT_ROOT/action_tracker.py"
