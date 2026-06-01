# E6-LS4: buffer-time-between-meetings

Find a 1-hour slot with 15-minute buffer before and after for each participant. Surface-level free time is not enough if buffer is violated.

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

Top-level keys:
- `recommendations` (array, required): ranked candidate slots. Use an empty array if you only write `scheduled_meetings`.
- `scheduled_meetings` (array, required): placed requested meetings. Use an empty array for this single-slot recommendation task.

Each object in `recommendations` must include:
- `slot_id` (string): stable identifier for the candidate slot.
- `start_utc` and `end_utc` (strings): ISO-8601 UTC timestamps ending in `Z`.
- `score` (integer): hard-constraint diagnostic score described below.
- `soft_preferences_met` (integer): number of soft preferences satisfied; use `0` when none apply.
- `preference_breakdown` (object): keys are participant IDs and values are booleans indicating whether that participant's applicable preference/constraint was satisfied for the slot.
- `local_times` (array of strings): one human-readable local-time evidence string per participant, including local time and time-zone abbreviation such as `EDT`; include any relevant offset evidence when DST matters.
- `reasons` (array of non-empty strings): concrete reasons explaining why the slot is valid.

Each object in `scheduled_meetings`, when used, must include the same fields, except use `meeting_id` (string) instead of `slot_id`.

Use real time-zone conversion, participant working hours, existing calendar events, required buffer time, hard constraints, and soft preferences. Exclude forbidden slots and explain ranked recommendations or scheduled meetings with concrete reasons.

For this buffer-focused task, `score` is a hard-constraint diagnostic score: add 1 when the candidate is inside every participant's working hours, and add 1 when the required 15-minute buffer is available before and after the meeting for every participant. There are no soft preferences in this instance, so `soft_preferences_met` should be 0 unless the input data explicitly adds preferences.
