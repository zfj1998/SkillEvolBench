# E6-LS1: sender-hierarchy-weight

Triage emails using the mailbox and org_chart.json. Sender role should inform business importance, but do not blindly promote emotional wording.

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

Classify every source email exactly once. Rank lower `rank` values first, with P0 before P1 before P2 before P3, and include concrete evidence in `reason`. If the task asks for replies, include only the messages that truly need responses in `response_list` and draft concise context-aware replies in `drafts`. Decide `needs_response` independently from priority: an explicit request to confirm, approve, review, decide, or reply can still need a response when optional wording lowers it to P2; pure FYI, automated, and newsletter messages do not.

Use these priority definitions:

- **P0**: an active production/security incident or a hard same-day/overnight
  deadline for which work must start immediately (including an explicit EOD
  deadline tied to a concrete same-day customer, signature, payment,
  production, or security blocker);
- **P1**: a material action, review, approval, or near-term deliverable that
  should be handled today but is not an active incident or hard same-day
  blocker;

A clock or senior sender alone does not make a message P0. Routine reviews,
readouts, approvals, and decisions requested today or by tomorrow are P1 unless
the message shows that missing the deadline directly blocks a customer,
signature, payment, production, or security outcome. Use P0 only when work must
start immediately to prevent that concrete blocking outcome.

- **P2**: useful status, timeline, or background information with no immediate
  action;
- **P3**: low-impact administrative, social, promotional, automated, or
  newsletter content.
