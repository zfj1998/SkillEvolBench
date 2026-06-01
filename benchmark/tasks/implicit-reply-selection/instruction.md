# E6-LS2: implicit-reply-selection

Handle these 10 emails appropriately. Some require replies, some only need acknowledgement, and some should be ignored.

Update or run the included reply pipeline and write `output/replies.json`.
Use the thread export under `mail/`, structured context under `context/`, and calendar/availability files where present.

## Output Contract
Write `output/replies.json` as JSON with this schema:

```json
{
  "actions": [
    {"email_id": "source email id", "action": "reply|acknowledge|ignore", "reason": "why this action was selected"}
  ],
  "replies": [
    {"email_id": "source email id", "to": ["email"], "cc": ["email"], "body": "substantive reply", "rationale": "context used"}
  ],
  "acknowledgements": [
    {"email_id": "source email id", "to": ["email"], "cc": ["email"], "body": "short acknowledgement", "rationale": "why an acknowledgement is enough"}
  ],
  "ignored": [
    {"email_id": "source email id", "reason": "why no response is needed"}
  ]
}
```

Choose `reply` only for messages requiring a substantive answer, `acknowledge` for FYI/closure messages that merit a short receipt, and `ignore` for newsletters or automated/no-action items. Reply bodies must use the provided thread history, project context, stakeholder context, and calendar context, preserve relevant CC recipients, and avoid making unsupported commitments.

For this task instance, derive the exact per-email action from the provided mail/context files rather than applying one action to all messages. Substantive replies must mention the concrete facts requested by the source email, acknowledgements should be short receipt-style responses, and ignored messages should be automated or no-action items with a reason.

Keep the action-selection policy auditable: it should separately justify messages selected for substantive `reply`, lightweight `acknowledge`, and `ignore`, because the verifier checks that the ten emails are not handled with a single blanket response.
