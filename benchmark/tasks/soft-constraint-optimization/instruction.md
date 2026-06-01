# E6-LS4: soft-constraint-optimization

Rank these 3 hard-feasible slots by how well they satisfy team preferences. Use preferences.json.

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

For this task, the provided candidate slots are already hard-feasible. Rank those candidates by soft preferences. Include `score`, `soft_preferences_met`, participant-level `preference_breakdown`, and concrete `reasons` explaining which participant preferences matched or missed.

Preference scoring for this task is one point per satisfied participant preference, and `score` should equal `soft_preferences_met`. Interpret `prefer_morning` as the participant's local start time before 12:00, `avoid_friday` as any non-Friday local meeting day, and Charlie's office-day preference from `preferences.json` as Tuesday or Friday. The `preference_breakdown` map should contain each participant id with `true` or `false`.
