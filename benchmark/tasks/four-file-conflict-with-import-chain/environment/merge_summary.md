# Merge Summary

Branches involved:
- `mainline/refactor-helper-name`
- `feature/add-mode-param`

Notes from review:
- Alice renamed `helper_func` to `process_data` because the helper is now used outside the original import chain.
- Bob added a `mode` parameter so API callers and the service layer can choose stricter processing rules.
- The service path is expected to keep using strict mode for cacheable backend work.
- The request handlers should accept an optional `mode` field from incoming payloads.

Definition of done:
- No conflict markers remain.
- The renamed helper is the one exported by the module.
- The new parameter is preserved everywhere that needs it.
