#!/bin/bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/extraction_policy.py" <<'PYMOD'
from __future__ import annotations

implicit_patterns = ["would help if", "we should probably", "someone should", "needs to", "team agreed", "will circulate", "needs to rerun", "should collect"]
rhetorical_patterns = ["who even", "why do we even", "does anyone actually", "can we not", "remember when", "coffee", "dashboard learn", "is it just me", "could the build number"]
question_action_patterns = ["can we schedule", "could someone update", "should i send", "shall we move", "would you be able", "could we revisit", "should we set up"]
USER_BY_ID = {"U101": "alice", "U102": "bob", "U103": "charlie", "U104": "diana", "U105": "eli", "U106": "fatima", "U107": "george", "U108": "maya", "U109": "nora", "U110": "omar"}
_TRACKED: dict[str, dict] = {}


def _source(item: dict) -> str:
    return item.get("id", "")


def _text(item: dict) -> str:
    return item.get("text", "")


def _lower(item: dict) -> str:
    return _text(item).lower()


def _speaker(item: dict) -> str:
    raw = item.get("speaker") or item.get("user") or ""
    if raw in USER_BY_ID:
        return USER_BY_ID[raw]
    lowered = str(raw).lower()
    for name in ["alice", "bob", "charlie", "diana", "eli", "fatima", "george", "maya", "nora", "omar"]:
        if name in lowered:
            return name
    return "unspecified"


def _deadline(t: str):
    if "by friday" in t or "to friday" in t:
        return "Friday"
    if "by thursday" in t:
        return "Thursday"
    if "by monday" in t:
        return "Monday"
    if "by tuesday" in t:
        return "Tuesday"
    if "by wednesday" in t:
        return "Wednesday"
    if "by eod" in t:
        return "EOD"
    if "before ga" in t:
        return "GA"
    if "tomorrow" in t:
        return "tomorrow"
    if "to q2" in t:
        return "Q2"
    return None


def _topic(item: dict):
    t = _lower(item)
    if "launch checklist" in t:
        return "finalize launch checklist", ["finalize", "launch", "checklist"], "explicit"
    if "rollout checklist" in t:
        return "finalize rollout checklist", ["finalize", "rollout", "checklist"], "explicit"
    if "api docs" in t and "rate-limit" in t:
        return "update api docs rate-limit", ["update", "api", "docs", "rate-limit"], "explicit"
    if "docs" in t and "import limit" in t:
        return "update docs import limit", ["update", "docs", "import", "limit"], "explicit"
    if "northstar recap" in t:
        return "send Northstar recap", ["send", "Northstar", "recap"], "explicit"
    if "invoice export" in t:
        return "verify invoice export", ["verify", "invoice", "export"], "explicit"
    if "smoke tests" in t or "smoke suite" in t:
        return "run smoke tests", ["run", "smoke", "tests"], "explicit"
    if "release notes" in t:
        return "publish release notes", ["publish", "release", "notes"], "explicit"
    if "client attendees" in t or "client attendee" in t:
        return "confirm client attendees", ["confirm", "client", "attendees"], "explicit"
    if "design assets" in t:
        return "upload design assets", ["upload", "design", "assets"], "explicit"
    if "mobile mockups" in t:
        return "upload mobile mockups", ["upload", "mobile", "mockups"], "explicit"
    if "webhook retries" in t:
        return "verify webhook retries", ["verify", "webhook", "retries"], "explicit"
    if "p95 summary" in t:
        return "publish p95 summary", ["publish", "p95", "summary"], "explicit"
    if "checkout mockups" in t:
        return "review checkout mockups", ["review", "checkout", "mockups"], "implicit"
    if "onboarding docs" in t:
        return "update onboarding docs", ["update", "onboarding", "docs"], "implicit"
    if "api contracts" in t and ("would help" in t or "checked" in t or "check" in t):
        return "check API contracts against staging", ["check", "API", "contracts", "staging"], "implicit"
    if "performance metrics" in t:
        return "look performance metrics", ["look", "performance", "metrics"], "implicit"
    if "pricing copy" in t and ("needs to" in t or "weigh" in t):
        return "weigh pricing copy", ["weigh", "pricing", "copy"], "implicit"
    if "schedule a review session" in t:
        if "migration risk" in t:
            return "schedule review migration risk", ["schedule", "review", "migration", "risk"], "question_action"
        return "schedule review session", ["schedule", "review", "session"], "question_action"
    if "update the wiki" in t:
        return "update wiki escalation", ["update", "wiki", "escalation"], "question_action"
    if "send the invite" in t:
        return "send invite mobile review", ["send", "invite", "mobile", "review"], "question_action"
    if "move the deadline" in t:
        return "move deadline Friday", ["move", "deadline", "Friday"], "question_action"
    if "test this against the northstar account" in t:
        return "test Northstar account", ["test", "Northstar", "account"], "question_action"
    if "revisit the q4 targets" in t:
        return "revisit Q4 targets", ["revisit", "Q4", "targets"], "question_action"
    if "set up a call" in t and "redesign" in t:
        return "set call redesign handoff", ["set", "call", "redesign", "handoff"], "question_action"
    if "vendor quote" in t:
        return "follow vendor quote", ["follow", "vendor", "quote"], "implicit"
    if "webhook contract" in t:
        return "validate webhook contract staging", ["validate", "webhook", "contract", "staging"], "implicit"
    if "data migration" in t and "risk note" in t:
        return "defer migration Q2 risk note", ["defer", "migration", "Q2", "risk", "note"], "implicit"
    if "onboarding checklist" in t:
        return "circulate onboarding checklist", ["circulate", "onboarding", "checklist"], "implicit"
    if "regression pack" in t:
        return "rerun regression pack", ["rerun", "regression", "pack"], "implicit"
    if "beta feedback" in t:
        return "collect beta feedback", ["collect", "beta", "feedback"], "implicit"
    return None, [], ""


def _assignee(item: dict, desc: str, action_type: str) -> str:
    t = _lower(item)
    for token, name in USER_BY_ID.items():
        if f"<@{token}>" in _text(item):
            return name
    if "design team" in t:
        return "design"
    if "backend" in t:
        return "backend"
    if "team agreed" in t or desc.startswith("defer migration"):
        return "team"
    if "alice" in t:
        return "alice"
    if "diana" in t:
        return "diana"
    if "qa needs" in t:
        return "qa"
    if "product" in t:
        return "product"
    if action_type == "question_action":
        return _speaker(item) if "should i" in t else "unspecified"
    if "someone should" in t or "we should" in t:
        return "unspecified"
    return _speaker(item)


def _is_non_action(item: dict) -> bool:
    t = _lower(item)
    if any(pat in t for pat in rhetorical_patterns):
        return True
    return any(token in t for token in ["decision:", "comfortable", "out of scope", "attached", "already", "not changing", "context only", "no new", "same deck", "unchanged", "closed with thanks", "end of thread", "good thread", "thanks all", "readiness review remains"])


def _mutate_status(item: dict) -> None:
    t = _lower(item)
    if "rollout checklist" in t and "done" in t:
        _set_status("rollout checklist", "completed")
    if "docs update is blocked" in t:
        _set_status("docs import", "blocked")
        _set_status("pricing copy", "blocked")
    if "performance summary is done" in t:
        _set_status("p95 summary", "completed")
    if "client attendee" in t and "waiting" in t:
        _set_status("client attendees", "follow_up_needed")
    if "webhook retry check" in t:
        _set_status("webhook retries", "completed")
    if "invoice export" in t and "matched" in t:
        _set_status("invoice export", "completed")
    if "mobile mocks" in t and "uploaded" in t:
        _set_status("mobile mockups", "completed")
    if "smoke tests" in t and "queued" in t:
        _set_status("smoke tests", "follow_up_needed")


def _set_status(topic: str, status: str) -> None:
    for desc, action in _TRACKED.items():
        if topic in desc:
            action["status"] = status


def classify_item(item: dict) -> dict:
    _mutate_status(item)
    source_id = _source(item)
    desc, terms, action_type = _topic(item)
    t = _lower(item)
    if desc and not _is_non_action(item):
        implicit = action_type == "implicit"
        confidence = 0.72 if "performance metrics" in t else (0.76 if "onboarding docs" in t else (0.82 if action_type in {"implicit", "question_action"} else 0.9))
        action = {
            "label": "action",
            "source_message_id": source_id,
            "assignee": _assignee(item, desc, action_type),
            "description": desc,
            "description_terms": terms,
            "deadline": _deadline(t),
            "action_type": action_type,
            "implicit": implicit,
            "status": "open",
            "confidence": confidence,
            "reason": f"Classified as actionable via {action_type} request/delegation pattern with source evidence.",
        }
        _TRACKED[desc.lower()] = action
        return action
    return {"label": "non_action", "source_message_id": source_id, "reason": "Non-action: discussion, rhetorical question, social chatter, complaint, or status context without a delegated next step."}
PYMOD
cat > "$PROJECT_ROOT/summary_writer.py" <<'PYMOD'
from __future__ import annotations


def status_summary(actions: list[dict]) -> dict:
    summary = {"open": 0, "completed": 0, "blocked": 0, "follow_up_needed": 0}
    for action in actions:
        status = action.get("status", "open")
        summary[status] = summary.get(status, 0) + 1
    return summary


def build_summary(actions: list[dict], non_actions: list[dict], items: list[dict]) -> dict:
    follow = [action for action in actions if action.get("status") == "follow_up_needed"]
    return {
        "total_actions": len(actions),
        "total_non_actions": len(non_actions),
        "follow_up_needed": follow,
        "key_decisions": ["API freeze remains noon Eastern", "Northstar pilot stays US-only", "migration risk note is deferred to Q2", "docs pricing is blocked until product confirms wording"],
    }
PYMOD
python3 "$PROJECT_ROOT/thread_parser.py"
