# Response formats

Canonical response contract:

- Legacy format:
  - `{"status":"ok","data":[...]}`
- Current rollout format:
  - `{"status":"ok","result":{"items":[...],"meta":{...}}}`

Compatibility note:
- Some canary responses still include a top-level `data` field for old clients.
- When `result.items` is present, treat that nested collection as the source of truth.
