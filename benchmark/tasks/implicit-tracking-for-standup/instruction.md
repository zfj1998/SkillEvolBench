# E6-LS3: implicit-tracking-for-standup

Prepare the weekly standup update based on last week's commitments and this week's status evidence.

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

For this standup bundle, the expected actions include the webhook patch, pricing page, EMEA sandbox, customer FAQ, regression runs, docs update, migration notes, and partner call. Normalize visible deadlines from the Slack evidence, including the Wednesday webhook-patch deadline, the Friday pricing/FAQ/regression/partner-call deadlines, and the end-of-month docs deadline. Later messages should update statuses: completed items include the webhook patch, EMEA sandbox, and regression runs; delayed items include the pricing page and customer FAQ; items without a later update should remain no_update. Treat the EMEA sandbox, docs update, and migration notes as implicit commitments.
