# Task

Parse the thread completely: extract all actions, classify non-actions, track status, and summarize decisions.

The thread mixes explicit asks, implicit team delegation, genuine request-questions, rhetorical questions, decisions, completions, and blockers.

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

Keep the existing modular parser structure rather than replacing the task with a
static report. The implementation should preserve separate parser, context
loading, extraction policy, and summary-writing modules (`thread_parser.py`,
`context_loader.py`, `extraction_policy.py`, and `summary_writer.py`). The
extraction policy should explicitly handle:
- implicit delegation patterns such as "Would help if ...", "We should ...",
  "team could ...", or "someone should ...";
- actionable request questions such as "Would you be able ...", "Should I ...",
  "Could someone ...", or requests to schedule/review/test/update;
- rhetorical or non-action questions such as complaints, jokes, or process
  commentary that do not create ownership;
- status updates that mark earlier actions as completed, blocked, open, or
  needing follow-up.

Process all 50 source messages, keep per-source classifications, and ensure the
summary captures key decisions and follow-up needs from the thread.
