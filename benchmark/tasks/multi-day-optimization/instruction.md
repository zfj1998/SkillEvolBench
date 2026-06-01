# E6-LS4: multi-day-optimization

Schedule these 3 meetings across next week. Minimize fragmentation, respect hard constraints, and satisfy soft preferences where possible.

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

For this multi-meeting task, first satisfy hard constraints for every attendee in their local time zone, then score each scheduled meeting for auditability. Add 1 point for hard-feasible placement, add 1 point when that meeting's own preference in `preferences.json` is satisfied, and add 1 extra point for the client demo when it also lands in a reasonable London customer afternoon. `soft_preferences_met` counts only meeting-specific preferences, while the global `spread_across_days` preference should be explained in `reasons` and used to avoid stacking the three meetings onto one day.
