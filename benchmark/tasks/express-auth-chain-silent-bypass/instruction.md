# Close the auth bypass in the FinGuard API

The Node service is in `/root/task`. Security found that some specially crafted bearer tokens can still get `HTTP 200` from protected endpoints and return real user data. We are not seeing a crash or traceback for this one.

Please fix the actual bug in the existing code under `/root/task` so protected routes reject bad tokens correctly and normal valid tokens still work. Save your edits in `/root/task`.

Expected API behavior:
- `GET /api/health` and `GET /api/version` are public JSON endpoints.
- Protected endpoints require `Authorization: Bearer <token>`.
- Valid tokens are three base64url segments signed with HMAC-SHA256 by `signToken` in `/root/task/middleware/tokenValidator.js`; claims must include `sub` and `role`.
- Missing, malformed, expired, invalidly encoded, invalid JSON, missing-claim, or bad-signature tokens must return an error JSON object shaped like `{ "error": <string>, "code": <string> }` with a non-200 status, and that response must not include user data fields such as `users`, `user`, `email`, `phone`, `ssn_last4`, or `account_balance`.
- Rejected malformed or invalid tokens should also produce a warning-level diagnostic on stderr or the service logger so security can audit rejected token attempts without exposing protected data.
- Insufficient-role requests must return `403` with the same error object shape and no protected user data.
- `GET /api/users` returns `{ "users": [...], "count": <number>, "filtered": <boolean> }` for viewer-or-higher roles. Each non-admin user object should include only public fields (`id`, `username`, `role`, `department`, `created_at`), except analyst responses may also include `email`.
- `GET /api/admin/users` returns `{ "users": [...], "count": <number>, "includes_sensitive": true, ... }` only for admin tokens. Admin user objects may include all stored fields, including `email`, `phone`, `ssn_last4`, and `account_balance`; viewer or analyst tokens should receive `403`.

Good places to start:
- `/root/task/middleware/tokenValidator.js`
- `/root/task/middleware/roleChecker.js`
- `/root/task/routes/api.js`

Deliverable note: no standalone output file is required. The required artifacts are the edited Node service files under `/root/task`; the verifier checks HTTP status codes and JSON response shapes from the existing API endpoints.
