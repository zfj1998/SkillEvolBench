# E6-LS4: 4-person-3-timezone

Find available 1-hour meeting slots for all 4 participants within their working hours (9am-5pm local unless otherwise specified). Use the JSON and ICS calendar exports.

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

Use real time-zone conversion and each participant's working hours. For this task instance there are four participants across Eastern, Pacific, and Central European time zones. Rank feasible 1-hour candidates by the number of included participants who can attend during working hours, after excluding busy calendar conflicts. There is no nonzero buffer requirement and no soft-preference bonus for this instance, so `soft_preferences_met` should be `0` for a purely hard-constraint recommendation.

Exclude any slot outside participant working hours, include local-time evidence in the output, and explain ranked recommendations with concrete reasons.
