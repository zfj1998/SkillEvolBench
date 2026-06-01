# E6-LS3: full-thread-extract-track-followup

Extract all action items, track their status, flag overdue commitments, and draft polite follow-up emails for overdue items.

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

Extract explicit commitments and implied commitments, ignore rhetorical questions and background chatter, normalize relative dates using the supplied current-date context, and update each action status from later status messages. Use `description_terms` to expose the key evidence terms for each normalized description; use `confidence` to distinguish strong explicit commitments from weaker implicit commitments; keep `summary` counts consistent with action statuses. Draft follow-ups only for items that need a polite status check.

Use `context/current_date.json` as the anchor for relative dates. In this fixture, phrases like "last Monday" and "last Wednesday" are relative to the supplied current date, and later Slack updates such as completion, delay, blocker, or revised ETA messages should override the initial open status for the related action.
