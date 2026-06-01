# Task

Extract all action items from the Slack launch thread.

The thread contains explicit asks, launch decisions, status context, and casual chatter.

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

Process every source Slack message. For this task, extract the explicit assignments in the launch thread and distinguish them from decisions, status-only updates, discussion, and social chatter while preserving source IDs and providing reasons. The output schema is shared with harder thread tasks, but the expected actions here are explicit rather than implicit.

The environment is intentionally organized as a small modular parser. Keep the
parsing, context loading, extraction policy, and summary writing pieces usable
rather than replacing the task with a one-off static JSON file. For this
canonical fixture, an action is an explicit assignment with an assignee and
actionable work, often paired with a deadline. Rhetorical questions, decisions,
status updates, social chatter, and side-conversation prompts should be recorded
as non-actions with a reason. Process all 20 source messages so the action and
non-action counts reconcile with the source export.
