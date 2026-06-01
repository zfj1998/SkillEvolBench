# E6-LS3: overdue-detection-with-dates

Track these commitments and flag overdue items using current_date 2026-04-23. Normalize relative dates before comparing.

Write `output/actions.json` using the provided Slack export and tracking pipeline.

## Output Contract
Write `output/actions.json` as JSON with this schema:

```json
{
  "actions": [
    {
      "id": "stable action id",
      "source_message_id": "Slack message id",
      "description": "normalized action description",
      "description_terms": ["key terms that should appear in the description"],
      "assignee": "owner name or team",
      "deadline": "YYYY-MM-DD or null",
      "status": "open|completed|delayed|overdue|no_update",
      "confidence": 0.0,
      "implicit": false,
      "reason": "evidence for extraction/status"
    }
  ],
  "followups": [
    {"action_id": "stable action id", "to": "assignee", "body": "polite follow-up"}
  ],
  "summary": {"total_actions": 0, "completed": 0, "delayed": 0, "overdue": 0, "no_update": 0}
}
```

Extract explicit commitments and implied commitments, ignore rhetorical questions and background chatter, and normalize relative dates using the supplied current-date context. In this task instance there are no later completion or delay messages for the tracked commitments, so statuses are determined by comparing each normalized deadline with current date `2026-04-23`: past-due items are `overdue`, and future items remain `open`.

Use `description_terms` to expose the key evidence terms for each normalized description; use `confidence` to distinguish strong explicit commitments from weaker implicit commitments; keep `summary` counts consistent with action statuses. Draft follow-ups only for items that need a polite status check.

Use `context/current_date.json` as the source of truth for the date anchor. Resolve weekday phrases such as "last Monday" and "last Wednesday" to the most recent matching weekday before the current date, and resolve quarter references using the 2026 calendar year.
