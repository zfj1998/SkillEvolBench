# E6-LS2: friendly-tone-unreasonable-request-trap

Draft a reply to this request. Keep the relationship warm while evaluating whether the requested scope and timeline are realistic.

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

For this task, the reply policy should explicitly evaluate scope, timeline, and whether the requested commitment is realistic. Keep the tone warm, but do not promise an infeasible full rewrite by Friday; offer a staged or narrower alternative grounded in the provided project context.
