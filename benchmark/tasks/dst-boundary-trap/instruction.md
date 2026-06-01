# E6-LS4: dst-boundary-trap

Schedule a meeting for March 15 between New York and London teams. Do not assume fixed UTC offsets across DST boundaries.

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

Use real time-zone conversion, participant working hours, existing calendar events, required buffer time, hard constraints, and soft preferences. Exclude forbidden slots and explain ranked recommendations or scheduled meetings with concrete reasons.

For this DST-focused task, `score` is a hard-constraint diagnostic score: add 1 when the slot is within both teams' local working hours, and add 1 when the local-time evidence is computed with real IANA time zones rather than fixed offsets. Include local-time evidence showing that March 15, 2023 is EDT in New York, GMT in London, and a 4-hour New York/London offset. There are no soft preferences in this instance, so `soft_preferences_met` should be 0 unless the input data explicitly adds preferences.
