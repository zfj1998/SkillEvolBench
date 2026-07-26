# E6-LS1: implicit-urgency-30-emails

Triage these 30 emails by priority. Explain the evidence for each priority, including signals that are only implied by timing, external stakeholders, or repeated follow-up.

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

Use these priority definitions:

- **P0**: an active production/security incident or a hard same-day/overnight
  deadline for which work must start immediately (including an explicit EOD
  deadline or a same-day customer/signature blocker);
- **P1**: a material action, review, approval, or near-term deliverable that
  should be handled today but is not an active incident or hard same-day
  blocker;
- **P2**: useful status, timeline, or background information with no immediate
  action;
- **P3**: low-impact administrative, social, promotional, automated, or
  newsletter content.
