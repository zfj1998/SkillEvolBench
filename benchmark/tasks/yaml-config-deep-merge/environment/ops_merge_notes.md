# Ops Merge Notes

Branches involved:
- `ops/tune-db-pool`
- `security/enable-db-ssl`

Deployment expectation:
- Prod should use a larger pool size than staging.
- SSL must stay under the database section because the app reads `config["database"]["ssl"]`.

Reminder:
- This file is consumed both by the application loader and by a deploy-time config validation step.
- A text merge that "looks right" can still be structurally wrong if the indentation changes the nesting.
