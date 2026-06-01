# Task

Extract action items from these messages.

All messages are questions, but several are rhetorical, social, or complaints.

Write a structured JSON result to `output/thread_actions.json`. Include `actions`,
`non_actions`, `status_summary`, and `summary` fields. Preserve source message
IDs so reviewers can audit every extracted action.

## Output Contract
Write `output/thread_actions.json` as JSON with this schema:

```json
{
  "actions": [
    {
      "label": "action",
      "source_message_id": "source id",
      "assignee": "owner or team",
      "description": "normalized action",
      "deadline": "deadline text or null",
      "action_type": "explicit|implicit|question_action",
      "implicit": false,
      "status": "open|completed|blocked|follow_up_needed",
      "confidence": 0.0,
      "reason": "evidence for classification"
    }
  ],
  "non_actions": [
    {"label": "non_action", "source_message_id": "source id", "reason": "why this is discussion/chatter/rhetorical/status only"}
  ],
  "classifications": ["one classification object per source item"],
  "processed_count": 0,
  "source_count": 0,
  "status_summary": {"open": 0, "completed": 0, "blocked": 0, "follow_up_needed": 0},
  "summary": {"key_decisions": [], "follow_up_needed": []}
}
```

Process every source Slack message or meeting paragraph. Distinguish explicit assignments, implicit delegations, actionable questions, rhetorical questions, status-only updates, and social chatter while preserving source IDs and providing reasons.

