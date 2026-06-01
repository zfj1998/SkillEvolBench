# E6-LS2: multi-stakeholder-cc-balance

Draft a reply to the sales VP's email. Consider all recipients and avoid making commitments that engineering/product cannot support.

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

For this multi-stakeholder request, the substantive reply must explicitly balance Sales urgency with Engineering/Product feasibility: preserve the relevant Engineering and Product CC recipients, acknowledge customer pressure/momentum, avoid an unsupported full commitment, offer a staged MVP alternative for the top three rules within the near-term window, and mention the longer full-build estimate from context. Avoid overpromising phrases such as committing the full request outright, and avoid dismissive wording that shuts down the stakeholder.
