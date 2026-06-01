# E6-LS3: question-masquerading-as-action-trap

Extract action items from these messages. Distinguish real requests from rhetorical or social questions.

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

Extract explicit commitments and implied commitments, ignore rhetorical questions and background chatter, normalize relative dates using the supplied current-date context, and update each action status from later status messages. Use `description_terms` to expose the key evidence terms for each normalized description; use `confidence` to distinguish strong explicit commitments from weaker implicit commitments; keep `summary` counts consistent with action statuses, including an `open` count when actions remain open. Draft follow-ups only for items that need a polite status check.

For this fixture, the main challenge is that several messages are phrased as questions but only some are real requests. Keep the existing action-tracking pipeline and implement the distinction in the policy modules rather than writing a static JSON file. The policy logic should explicitly handle:
- rhetorical questions that express frustration or social commentary and do not create ownership;
- genuine request questions that ask someone to schedule, revisit, call, clean up, review, or otherwise perform work;
- ordinary background chatter that should remain out of the action list.

The expected real requests are the Q4 targets planning session, the Northstar call, and the notes cleanup request. The coffee/process commentary questions are non-actions. Use process logic that makes this distinction auditable with clear `reason` text and source message IDs.
