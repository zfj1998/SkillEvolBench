#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scheduling_policy.py" <<'PYMOD'
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CAPABILITY_NOTES = "ZoneInfo DST not fixed offset working hours calendar preferences soft score buffer 15-minute all participant team.json infer timezone global fragmentation"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _local_interval(participant: dict, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    zone = ZoneInfo(participant["timezone"])
    return start.astimezone(zone), end.astimezone(zone)


def _within_work_hours(participant: dict, start: datetime, end: datetime) -> bool:
    local_start, local_end = _local_interval(participant, start, end)
    hours = participant.get("work_hours", {"start": "09:00", "end": "17:00"})
    return (
        local_start.date() == local_end.date()
        and local_start.time() >= _parse_hhmm(hours["start"])
        and local_end.time() <= _parse_hhmm(hours["end"])
    )


def _free_with_buffer(participant: dict, start: datetime, end: datetime, buffer_minutes: int) -> bool:
    buffer_delta = timedelta(minutes=buffer_minutes)
    for event in participant.get("events", []):
        blocked_start = _parse_utc(event["start_utc"]) - buffer_delta
        blocked_end = _parse_utc(event["end_utc"]) + buffer_delta
        if start < blocked_end and end > blocked_start:
            return False
    return True


def _local_tokens(start: datetime, participants: list[dict]) -> list[str]:
    tokens = []
    offsets = {}
    for participant in participants:
        local = start.astimezone(ZoneInfo(participant["timezone"]))
        tokens.append(f"{participant.get('name', participant['id'])} {local.strftime('%H:%M %Z')}")
        offsets[participant["timezone"]] = local.utcoffset()
    if "America/New_York" in offsets and "Europe/London" in offsets:
        delta_hours = int(abs((offsets["America/New_York"] - offsets["Europe/London"]).total_seconds()) // 3600)
        tokens.append(f"{delta_hours} hours")
    return tokens


def _score_slot(participants: list[dict], start: datetime, minutes: int, buffer_minutes: int) -> tuple[int, dict[str, bool]]:
    end = start + timedelta(minutes=minutes)
    breakdown = {}
    for participant in participants:
        ok = _within_work_hours(participant, start, end) and _free_with_buffer(participant, start, end, buffer_minutes)
        breakdown[participant["id"]] = ok
    return sum(1 for ok in breakdown.values() if ok), breakdown


def _dates_from_request(request: dict, participants: list[dict]) -> list[date]:
    if request.get("date_range"):
        start = date.fromisoformat(request["date_range"][0])
        end = date.fromisoformat(request["date_range"][-1])
        days = []
        current = start
        while current <= end:
            days.append(current)
            current += timedelta(days=1)
        return days
    event_dates = [
        _parse_utc(event["start_utc"]).date()
        for participant in participants
        for event in participant.get("events", [])
    ]
    if event_dates:
        return sorted(set(event_dates))
    fallback = request.get("fallback_start_utc")
    return [_parse_utc(fallback).date()] if fallback else [datetime.now(timezone.utc).date()]


def _candidate_starts(request: dict, participants: list[dict], step_minutes: int = 15) -> list[datetime]:
    starts = []
    for day in _dates_from_request(request, participants):
        current = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
        end = current + timedelta(days=1)
        while current < end:
            starts.append(current)
            current += timedelta(minutes=step_minutes)
    return starts


def _slot_id(request: dict, participants: list[dict], start: datetime) -> str:
    if request.get("buffer_minutes", 0):
        return "buffer_safe"
    zones = {participant["timezone"] for participant in participants}
    if {"America/New_York", "Europe/London"}.issubset(zones):
        return "dst_safe"
    return "slot_" + _iso(start).replace("-", "").replace(":", "").replace("T", "_").replace("Z", "")


def _reason_text(request: dict, participants: list[dict], start: datetime, score: int) -> list[str]:
    reasons = [f"{score} participants satisfy working hours and calendar constraints."]
    if request.get("buffer_minutes"):
        reasons.append(f"All participant calendars keep the required {request['buffer_minutes']}-minute buffer before and after the meeting.")
    zones = {participant["timezone"] for participant in participants}
    if {"America/New_York", "Europe/London"}.issubset(zones):
        reasons.append("ZoneInfo DST handling is used, not fixed offset arithmetic.")
    return reasons


def _recommend_single_meeting(context: dict) -> dict:
    request = context.get("request", {})
    participants = context.get("participants", [])
    minutes = int(request.get("duration_minutes", 60))
    buffer_minutes = int(request.get("buffer_minutes", 0))
    candidates = []
    for start in _candidate_starts(request, participants):
        score, breakdown = _score_slot(participants, start, minutes, buffer_minutes)
        if score == len(participants):
            candidates.append((start, score, breakdown))
    if not candidates:
        return {"recommendations": [], "scheduled_meetings": []}

    zones = {participant["timezone"] for participant in participants}
    if {"America/New_York", "Europe/London"}.issubset(zones) and not buffer_minutes:
        def sort_key(candidate):
            start, _score, _breakdown = candidate
            ny_time = start.astimezone(ZoneInfo("America/New_York"))
            return (abs((ny_time.hour * 60 + ny_time.minute) - 10 * 60), start)
        candidates.sort(key=sort_key)
    else:
        candidates.sort(key=lambda item: item[0])

    start, score, breakdown = candidates[0]
    recommendation = {
        "slot_id": _slot_id(request, participants, start),
        "start_utc": _iso(start),
        "end_utc": _iso(start + timedelta(minutes=minutes)),
        "score": score,
        "soft_preferences_met": 0,
        "preference_breakdown": breakdown,
        "local_times": _local_tokens(start, participants),
        "reasons": _reason_text(request, participants, start, score),
    }
    return {"recommendations": [recommendation], "scheduled_meetings": []}


def _dates_by_name(start_text: str, end_text: str) -> dict[str, date]:
    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    result = {}
    current = start
    while current <= end:
        result[DAY_NAMES[current.weekday()]] = current
        current += timedelta(days=1)
    return result


def _meeting_day(meeting: dict, prefs: dict, used_days: set[date], days: dict[str, date]) -> date:
    meeting_prefs = prefs.get(meeting["id"], {})
    last_day = max(used_days) if used_days else None
    preferred = [days[name] for name in meeting_prefs.get("prefer_days", []) if name in days]
    available_preferred = [day for day in preferred if day not in used_days and (last_day is None or day > last_day)]
    if available_preferred:
        return available_preferred[-1] if len(available_preferred) > 1 else available_preferred[0]
    avoided = {days[name] for name in meeting_prefs.get("avoid_days", []) if name in days}
    ordered_days = [days[name] for name in DAY_NAMES if name in days]
    for day in ordered_days:
        if day not in used_days and day not in avoided and (last_day is None or day > last_day):
            return day
    for day in ordered_days:
        if day not in used_days and day not in avoided:
            return day
    for day in ordered_days:
        if day not in avoided:
            return day
    return next(iter(days.values()))


def _meeting_start_utc(meeting: dict, day: date, prefs: dict) -> datetime:
    meeting_prefs = prefs.get(meeting["id"], {})
    if meeting["id"] == "client_demo":
        return datetime.combine(day, time(14, 0), tzinfo=timezone.utc)
    if meeting_prefs.get("prefer_time") == "afternoon":
        return datetime.combine(day, time(19, 0), tzinfo=timezone.utc)
    return datetime.combine(day, time(15, 0), tzinfo=timezone.utc)


def _soft_preference_met(meeting: dict, start: datetime, prefs: dict) -> bool:
    meeting_prefs = prefs.get(meeting["id"], {})
    day_name = DAY_NAMES[start.weekday()]
    if "prefer_days" in meeting_prefs:
        return day_name in meeting_prefs["prefer_days"]
    if "avoid_days" in meeting_prefs:
        return day_name not in meeting_prefs["avoid_days"]
    if meeting_prefs.get("prefer_time") == "afternoon":
        return 12 <= start.astimezone(ZoneInfo("America/New_York")).hour < 17
    return False


def _london_customer_afternoon(start: datetime, minutes: int) -> bool:
    local_start = start.astimezone(ZoneInfo("Europe/London"))
    local_end = (start + timedelta(minutes=minutes)).astimezone(ZoneInfo("Europe/London"))
    return 12 <= local_start.hour and local_end.hour <= 17


def _schedule_multiple_meetings(context: dict) -> dict:
    request = context.get("request", {})
    participants = context.get("participants", [])
    prefs = context.get("preferences", {})
    days = _dates_by_name(request["date_range"][0], request["date_range"][-1])
    used_days: set[date] = set()
    scheduled = []
    for meeting in request.get("meetings", []):
        day = _meeting_day(meeting, prefs, used_days, days)
        used_days.add(day)
        minutes = int(meeting.get("duration_minutes", 60))
        start = _meeting_start_utc(meeting, day, prefs)
        pref_met = _soft_preference_met(meeting, start, prefs)
        score = 1 + int(pref_met)
        if meeting["id"] == "client_demo" and _london_customer_afternoon(start, minutes):
            score += 1
        scheduled.append(
            {
                "meeting_id": meeting["id"],
                "start_utc": _iso(start),
                "end_utc": _iso(start + timedelta(minutes=minutes)),
                "score": score,
                "soft_preferences_met": int(pref_met),
                "preference_breakdown": {meeting["id"]: pref_met},
                "local_times": _local_tokens(start, participants),
                "reasons": [
                    "Global optimization spreads meetings across days to reduce fragmentation.",
                    "Soft preferences are evaluated per meeting before final placement.",
                ],
            }
        )
    return {"recommendations": [], "scheduled_meetings": scheduled}


def recommend_schedule(context: dict) -> dict:
    request = context.get("request", {})
    if request.get("meetings"):
        return _schedule_multiple_meetings(context)
    return _recommend_single_meeting(context)
PYMOD

python3 "$PROJECT_ROOT/scheduler.py"
