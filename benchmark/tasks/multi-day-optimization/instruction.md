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

For this multi-meeting task, each meeting's `attendee_ids` field defines the
people whose calendars and local working hours apply to that meeting. First
satisfy hard constraints for every attendee in their local time zone, then score
each scheduled meeting for auditability. Add 1 point for hard-feasible
placement, add 1 point when that meeting's own preference in
`preferences.json` is satisfied, and add 1 extra point for the client demo when
it also lands in a reasonable London customer afternoon (12:00 through 17:00
local time, including the meeting end). `soft_preferences_met` counts only
meeting-specific preferences.

Use the following public optimization order so equivalent solutions are
deterministic:

1. satisfy all hard constraints;
2. maximize the number of meeting-specific preferences satisfied;
3. maximize the client-demo London-afternoon bonus;
4. when `spread_across_days` is true, maximize the number of distinct meeting
   dates;
5. break remaining ties by the lexicographically earliest tuple of UTC starts
   in the input meeting order.

Return `scheduled_meetings` in the same order as the request. Explain the global
spread decision in `reasons`.
