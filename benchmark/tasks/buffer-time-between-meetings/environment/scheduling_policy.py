from __future__ import annotations
from datetime import datetime, timedelta, timezone

FIXED_OFFSETS = {
    "America/New_York": -5,
    "America/Los_Angeles": -8,
    "Europe/London": 0,
    "Europe/Berlin": 1,
}

def recommend_schedule(context: dict) -> dict:
    request = context.get("request", {})
    candidates = request.get("candidate_slots") or []
    if candidates:
        ranked = [{"slot_id": slot["id"], "start_utc": slot["start_utc"], "score": 0, "reasons": ["Starter keeps input order."]} for slot in candidates]
        return {"recommendations": ranked, "scheduled_meetings": []}
    # Starter proposes a generic noon ET slot and does not fully check all calendars, buffers, DST, or soft constraints.
    return {
        "recommendations": [{
            "slot_id": "starter_generic",
            "start_utc": request.get("fallback_start_utc", "2026-04-24T16:00:00Z"),
            "end_utc": request.get("fallback_end_utc", "2026-04-24T17:00:00Z"),
            "score": 0,
            "reasons": ["Generic fixed-offset scheduling guess."],
            "local_times": {},
        }],
        "scheduled_meetings": request.get("starter_scheduled_meetings", []),
    }
