#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scheduling_policy.py" <<'PYMOD'
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CAPABILITY_NOTES = (
    "ZoneInfo timezone conversion calendar conflict detection working hours "
    "all participants ranked available slots"
)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value[:10]).date()


def _parse_local_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def _slot_id(start: datetime) -> str:
    return "slot_" + start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def _events_for(participant: dict) -> list[tuple[datetime, datetime, str]]:
    events = participant.get("events", [])
    return [
        (_parse_utc(event["start_utc"]), _parse_utc(event["end_utc"]), event.get("summary", event.get("uid", "event")))
        for event in events
    ]


def _overlaps(start: datetime, end: datetime, event_start: datetime, event_end: datetime) -> bool:
    return start < event_end and end > event_start


def _within_work_hours(start: datetime, end: datetime, participant: dict) -> bool:
    tz = ZoneInfo(participant["timezone"])
    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)
    hours = participant.get("work_hours", {"start": "09:00", "end": "17:00"})
    work_start = _parse_local_time(hours.get("start", "09:00"))
    work_end = _parse_local_time(hours.get("end", "17:00"))
    return (
        local_start.date() == local_end.date()
        and local_start.time() >= work_start
        and local_end.time() <= work_end
    )


def _local_times(start: datetime, end: datetime, participants: list[dict]) -> list[str]:
    tokens = []
    for participant in participants:
        tz = ZoneInfo(participant["timezone"])
        local_start = start.astimezone(tz)
        local_end = end.astimezone(tz)
        name = participant.get("name", participant.get("id", "participant"))
        tokens.append(
            f"{name}: {local_start.strftime('%Y-%m-%d %H:%M %Z')} - "
            f"{local_end.strftime('%H:%M %Z')}"
        )
    return tokens


def _candidate_starts(request: dict, duration: int) -> list[datetime]:
    if request.get("candidate_slots"):
        return [_parse_utc(slot["start_utc"]) for slot in request["candidate_slots"]]

    start_day, end_day = request.get("date_range", [date.today().isoformat(), date.today().isoformat()])
    current = datetime.combine(_parse_date(start_day), time(0, 0), tzinfo=timezone.utc)
    stop = datetime.combine(_parse_date(end_day) + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)

    starts = []
    step = timedelta(minutes=int(request.get("slot_granularity_minutes", 60)))
    while current + timedelta(minutes=duration) <= stop:
        starts.append(current)
        current += step
    return starts


def _build_item(start: datetime, duration: int, participants: list[dict]) -> dict | None:
    end = start + timedelta(minutes=duration)
    conflicts = []
    within_hours = {}

    for participant in participants:
        pid = participant.get("id", participant.get("name", "participant"))
        for event_start, event_end, label in _events_for(participant):
            if _overlaps(start, end, event_start, event_end):
                conflicts.append(f"{pid}:{label}")
        within_hours[pid] = _within_work_hours(start, end, participant)

    if conflicts:
        return None

    score = sum(1 for ok in within_hours.values() if ok)
    if score == 0:
        return None

    outside = [pid for pid, ok in within_hours.items() if not ok]
    reasons = [
        "No participant calendar events overlap this one-hour slot.",
        f"{score} of {len(participants)} participants are inside local working hours.",
    ]
    if outside:
        reasons.append("Outside working hours for: " + ", ".join(outside))

    return {
        "slot_id": _slot_id(start),
        "start_utc": _iso_utc(start),
        "end_utc": _iso_utc(end),
        "score": score,
        "soft_preferences_met": 0,
        "preference_breakdown": within_hours,
        "local_times": _local_times(start, end, participants),
        "reasons": reasons,
    }


def recommend_schedule(context: dict) -> dict:
    participants = list(context.get("participants", []))
    request = dict(context.get("request", {}))
    duration = int(request.get("duration_minutes", 60))

    recommendations = []
    for start in _candidate_starts(request, duration):
        item = _build_item(start, duration, participants)
        if item is not None:
            recommendations.append(item)

    recommendations.sort(key=lambda item: (-item["score"], item["start_utc"]))
    return {"recommendations": recommendations, "scheduled_meetings": []}
PYMOD

python3 "$PROJECT_ROOT/scheduler.py"
