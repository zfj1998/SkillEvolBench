# E6-LS1: triage-then-draft-p0-replies

Triage emails. For P0 items only, draft immediate replies that acknowledge the issue, state the planned action, reference relevant thread context, and include an ETA.

Write your final triage result to `output/triage.json` by running or updating the included Python pipeline.
Use the mailbox export under `mail/`, contact context under `contacts/`, and any calendar/thread files provided.

## Output Contract
Write `output/triage.json` as JSON with this schema:

```json
{
  "items": [
    {
      "id": "message id from mail/messages.json",
      "thread_id": "source thread id",
      "subject": "original subject",
      "sender": "sender email",
      "priority": "P0|P1|P2|P3",
      "score": 0,
      "reason": "brief evidence-based explanation",
      "needs_response": false,
      "rank": 1
    }
  ],
  "response_list": ["message ids that need a response"],
  "drafts": [
    {"email_id": "message id", "to": ["email"], "cc": ["email"], "body": "reply text", "rationale": "why this reply is appropriate"}
  ],
  "summary": {"total": 0, "counts": {"P0": 0, "P1": 0, "P2": 0, "P3": 0}}
}
```

Classify every source email exactly once. Rank lower `rank` values first, with P0 before P1 before P2 before P3, and include concrete evidence in `reason`. If the task asks for replies, include only the messages that truly need responses in `response_list` and draft concise context-aware replies in `drafts`.

