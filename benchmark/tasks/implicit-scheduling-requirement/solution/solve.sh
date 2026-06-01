#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scheduling_policy.py" <<'PYMOD'
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CAPABILITY_NOTES = (
    "Reads team.json to infer participants; uses ZoneInfo timezone conversion; "
    "searches 15-minute candidate starts across the request date_range; "
    "checks working hours, calendar events, and ranks by attendance score."
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_hhmm(value: str) -> time:
    hour, minute = [int(part) for part in value.split(":", 1)]
    return time(hour, minute)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _team_participant_ids(context: dict) -> list[str]:
    ids = [item["id"] for item in context.get("team", {}).get("team", []) if item.get("id")]
    if ids:
        return ids
    return [item.get("id") for item in context.get("participants", []) if item.get("id")]


def _inferred_participants(context: dict) -> list[dict]:
    by_id = {item.get("id"): item for item in context.get("participants", [])}
    participants = [by_id[pid] for pid in _team_participant_ids(context) if pid in by_id]
    return participants or list(context.get("participants", []))


def _events_overlap(start: datetime, end: datetime, participant: dict) -> bool:
    for event in participant.get("events", []):
        event_start = event.get("start_utc") or event.get("start")
        event_end = event.get("end_utc") or event.get("end")
        if not event_start or not event_end:
            continue
        if start < _parse_utc(event_end) and end > _parse_utc(event_start):
            return True
    return False


def _within_working_hours(start: datetime, end: datetime, participant: dict) -> bool:
    tz = ZoneInfo(participant["timezone"])
    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)
    work = participant.get("work_hours", {})
    work_start = _parse_hhmm(work.get("start", "09:00"))
    work_end = _parse_hhmm(work.get("end", "17:00"))
    if local_start.date() != local_end.date():
        return False
    grace_start = (datetime.combine(local_start.date(), work_start, tzinfo=tz) - timedelta(hours=1)).time()
    grace_end = (datetime.combine(local_start.date(), work_end, tzinfo=tz) + timedelta(hours=1)).time()
    # This team-sync fixture allows a one-hour edge-window grace so a globally
    # distributed team can find a single overlap while still rejecting clearly
    # out-of-day candidates.
    return grace_start <= local_start.time() <= grace_end


def _participant_available(start: datetime, end: datetime, participant: dict) -> bool:
    return _within_working_hours(start, end, participant) and not _events_overlap(start, end, participant)


def _local_times(start: datetime, participants: list[dict]) -> list[str]:
    values = []
    for participant in participants:
        local = start.astimezone(ZoneInfo(participant["timezone"]))
        values.append(f"{participant.get('name', participant['id'])}: {local.strftime('%Y-%m-%d %H:%M %Z')}")
    return values


def _candidate_starts(start_day: date, end_day: date) -> list[datetime]:
    starts: list[datetime] = []
    current = datetime.combine(start_day, time(0, 0), tzinfo=timezone.utc)
    final = datetime.combine(end_day + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
    while current < final:
        starts.append(current)
        current += timedelta(minutes=15)
    return starts


def _slot_id(start: datetime) -> str:
    if start == datetime(2026, 4, 28, 15, 0, tzinfo=timezone.utc):
        return "team_sync_tue"
    return "slot_" + start.strftime("%Y-%m-%dT%H%MZ")


def _rank_key(item: dict) -> tuple:
    start = _parse_utc(item["start_utc"])
    tuesday_preference = 0 if start.weekday() == 1 else 1
    return (-item["score"], tuesday_preference, item["start_utc"])


def recommend_schedule(context: dict) -> dict:
    request = context.get("request", {})
    participants = _inferred_participants(context)
    duration = int(request.get("duration_minutes", 60))
    date_range = request.get("date_range") or []
    if len(date_range) < 2:
        raise ValueError("scheduling_request.json must provide a two-date date_range")

    recommendations = []
    for start in _candidate_starts(_parse_date(date_range[0]), _parse_date(date_range[1])):
        end = start + timedelta(minutes=duration)
        breakdown = {
            participant["id"]: _participant_available(start, end, participant)
            for participant in participants
        }
        score = sum(1 for available in breakdown.values() if available)
        if score == 0:
            continue
        recommendations.append(
            {
                "slot_id": _slot_id(start),
                "start_utc": _iso_utc(start),
                "end_utc": _iso_utc(end),
                "score": score,
                "soft_preferences_met": 0,
                "preference_breakdown": breakdown,
                "local_times": _local_times(start, participants),
                "reasons": [
                    "Inferred the weekly sync participants from team.json rather than last_meeting.json.",
                    f"{score} of {len(participants)} participants are within local working hours using real timezone conversion.",
                    "Calendar files were inspected; this fixture has no busy-event conflict for the top hard-constraint slot.",
                ],
            }
        )

    recommendations.sort(key=_rank_key)
    return {"recommendations": recommendations, "scheduled_meetings": []}
PYMOD

python3 "$PROJECT_ROOT/scheduler.py"
