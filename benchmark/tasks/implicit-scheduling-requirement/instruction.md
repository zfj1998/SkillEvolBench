# E6-LS4: implicit-scheduling-requirement

Schedule the weekly team sync for next week. Infer participants from team.json rather than only last week's attendee list.

Write `output/schedule.json` by running or updating the included scheduler pipeline.

## Output Contract
Write `output/schedule.json` as JSON with one or both of these top-level arrays:

```json
{
  "recommendations": [
    {
      "slot_id": "candidate or generated slot id",
      "start_utc": "ISO-8601 UTC start",
      "end_utc": "ISO-8601 UTC end",
      "score": 0,
      "soft_preferences_met": 0,
      "preference_breakdown": {"participant_id": true},
      "local_times": ["participant local time strings"],
      "reasons": ["why this slot satisfies constraints"]
    }
  ],
  "scheduled_meetings": [
    {
      "meeting_id": "requested meeting id",
      "start_utc": "ISO-8601 UTC start",
      "end_utc": "ISO-8601 UTC end",
      "score": 0,
      "soft_preferences_met": 0,
      "preference_breakdown": {"participant_id": true},
      "local_times": ["participant local time strings"],
      "reasons": ["why this meeting placement was chosen"]
    }
  ]
}
```

Use real time-zone conversion and infer the six required participants from `team.json`. Rank next-week 1-hour candidates by the number of inferred team participants who can attend during working hours. No nonzero buffer requirement or soft-preference bonus is active for this instance, so `soft_preferences_met` should be `0` for a purely hard-constraint recommendation. Calendar exports are provided as context, but this instance does not require resolving a conflicting busy event.

Generate candidate starts on 15-minute boundaries across the requested
`date_range`. For deterministic ranking, sort candidates by highest attendance
score first, then prefer the normal Tuesday weekly-sync day, then earlier UTC
start time. With the provided team and calendar context this should identify the
top recommendation as `2026-04-28T15:00:00Z` with all six inferred team
participants counted and `soft_preferences_met` equal to `0`.

Exclude any slot outside participant working hours, include local-time evidence,
and explain the recommendation with concrete reasons. The implementation should
read `team.json` to infer the participant set, use `ZoneInfo`/real time-zone
conversion, inspect the participant calendar files, and search/evaluate
candidates rather than returning a precomputed timestamp.
