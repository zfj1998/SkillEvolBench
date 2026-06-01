# E6-LS3: implicit-commitment-in-30-messages

Extract all commitments and action items, including implicit commitments. Calibrate confidence when language is tentative.

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

For this enriched implicit-commitment fixture, treat the following language as
commitment evidence even when it is not written as a formal action item:
- "Let me look into ..." creates an implicit owner commitment.
- "We should ..." or "We definitely need to ..." creates a team commitment when
  the work is launch-relevant.
- "I can probably help ..." is still an implicit commitment, but should receive
  lower confidence than a direct "I will ..." statement.
- "I'll circle back ..." creates an owner commitment.
- Direct "I will ..." language is explicit and should receive higher
  confidence.

The launch thread contains commitments around webhook retries, pricing copy,
migration mapping, customer quote wording, docs updates, and a load test. Keep
non-action questions and background notes out of the action list, and use stable
action IDs derived from the work being tracked.
