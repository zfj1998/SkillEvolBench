# Task

Extract action items from the meeting notes.

The notes mix decisions, discussion, jokes, and implied ownership. No paragraph is labeled Action.

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

Process every meeting paragraph. Distinguish explicit assignments, implied ownership or team decisions that create work, discussion-only paragraphs, jokes, and background context while preserving source IDs and providing reasons.

Keep the existing modular parser structure rather than replacing the task with a
static JSON file. The implementation should preserve separate parser, context
loading, extraction policy, and summary-writing modules (`thread_parser.py`,
`context_loader.py`, `extraction_policy.py`, and `summary_writer.py`). The
extraction policy should explicitly handle implied ownership, team decisions
that create work, discussion-only paragraphs, jokes, and non-actions.

Process all 30 meeting paragraphs. This fixture has six implied action items
hidden among discussion paragraphs; each action should include an inferred
assignee, source paragraph ID, reason, confidence, and status. Team decisions
that create work should be assigned to the relevant team rather than forced onto
a single person.
