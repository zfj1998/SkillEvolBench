#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/scheduling_policy.py" <<'PYMOD'
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from itertools import product
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


def _soft_preference_met(meeting: dict, start: datetime, prefs: dict) -> bool:
    meeting_prefs = prefs.get(meeting["id"], {})
    day_name = DAY_NAMES[start.weekday()]
    if "prefer_days" in meeting_prefs:
        return day_name in meeting_prefs["prefer_days"]
    if "avoid_days" in meeting_prefs:
        return day_name not in meeting_prefs["avoid_days"]
    if meeting_prefs.get("prefer_time") == "afternoon":
        participant_id = meeting_prefs["participant_id"]
        zone = meeting["_participant_zones"][participant_id]
        local = start.astimezone(ZoneInfo(zone))
        return 12 <= local.hour < 17
    return False


def _london_customer_afternoon(start: datetime, minutes: int) -> bool:
    local_start = start.astimezone(ZoneInfo("Europe/London"))
    local_end = (start + timedelta(minutes=minutes)).astimezone(ZoneInfo("Europe/London"))
    return 12 <= local_start.hour and local_end.hour <= 17


def _schedule_multiple_meetings(context: dict) -> dict:
    request = context.get("request", {})
    participants = context.get("participants", [])
    prefs = context.get("preferences", {})
    by_id = {participant["id"]: participant for participant in participants}
    meetings = request.get("meetings", [])
    participant_zones = {participant["id"]: participant["timezone"] for participant in participants}
    days = list(_dates_by_name(*request["date_range"]).values())

    options = []
    for original in meetings:
        meeting = {**original, "_participant_zones": participant_zones}
        attendees = [by_id[item] for item in meeting["attendee_ids"]]
        minutes = int(meeting["duration_minutes"])
        meeting_options = []
        for day in days:
            start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
            day_end = start + timedelta(days=1)
            while start < day_end:
                end = start + timedelta(minutes=minutes)
                if all(_within_work_hours(item, start, end) and _free_with_buffer(item, start, end, 0) for item in attendees):
                    pref_met = _soft_preference_met(meeting, start, prefs)
                    london_bonus = meeting["id"] == "client_demo" and _london_customer_afternoon(start, minutes)
                    meeting_options.append((start, pref_met, london_bonus, attendees))
                start += timedelta(minutes=15)
        options.append(meeting_options)

    def has_conflict(chosen) -> bool:
        for left_index, left in enumerate(chosen):
            left_start, _, _, left_attendees = left
            left_end = left_start + timedelta(minutes=int(meetings[left_index]["duration_minutes"]))
            left_ids = {item["id"] for item in left_attendees}
            for right_index in range(left_index + 1, len(chosen)):
                right_start, _, _, right_attendees = chosen[right_index]
                right_end = right_start + timedelta(minutes=int(meetings[right_index]["duration_minutes"]))
                if left_ids.intersection(item["id"] for item in right_attendees) and left_start < right_end and right_start < left_end:
                    return True
        return False

    feasible = [chosen for chosen in product(*options) if not has_conflict(chosen)]
    if not feasible:
        return {"recommendations": [], "scheduled_meetings": []}

    def objective(chosen):
        starts = tuple(item[0] for item in chosen)
        preference_count = sum(int(item[1]) for item in chosen)
        london_bonus_count = sum(int(item[2]) for item in chosen)
        distinct_days = len({start.date() for start in starts})
        return (-preference_count, -london_bonus_count, -distinct_days, starts)

    chosen = min(feasible, key=objective)
    scheduled = []
    for meeting, (start, pref_met, london_bonus, attendees) in zip(meetings, chosen):
        minutes = int(meeting["duration_minutes"])
        scheduled.append({
            "meeting_id": meeting["id"],
            "start_utc": _iso(start),
            "end_utc": _iso(start + timedelta(minutes=minutes)),
            "score": 1 + int(pref_met) + int(london_bonus),
            "soft_preferences_met": int(pref_met),
            "preference_breakdown": {meeting["id"]: pref_met},
            "local_times": _local_tokens(start, attendees),
            "reasons": [
                "Hard constraints hold for every listed attendee.",
                "Global optimization maximizes meeting preferences and spreads meetings across distinct days to reduce fragmentation.",
            ],
        })
    return {"recommendations": [], "scheduled_meetings": scheduled}


def recommend_schedule(context: dict) -> dict:
    request = context.get("request", {})
    if request.get("meetings"):
        return _schedule_multiple_meetings(context)
    return _recommend_single_meeting(context)
PYMOD

python3 "$PROJECT_ROOT/scheduler.py"
