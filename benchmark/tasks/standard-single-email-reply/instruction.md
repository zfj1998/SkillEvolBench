# E6-LS2: standard-single-email-reply

Draft a professional reply to this email. Use context/project_state.json and calendar availability.

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

For the substantive reply in this task, answer the sender's concrete questions using values from `context/project_state.json` and the calendar files: include the current progress percentage, approved budget amount, backend staffing status, the available Tuesday/Thursday meeting windows, the integration-testing status, and a next-meeting framing. Avoid generic filler such as "sounds good to me", "check on the details", or "follow up soon". The reply rationale should identify that the email asked three questions and should mention the project_state context used.
