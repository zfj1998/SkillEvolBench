# Replace the event switch with a strategy mapping without changing behavior

The event processor is under `/root/task`. Product wants the large `processEvent()` switch replaced with a strategy-style mapping so new event types are easier to add.

Please refactor the existing implementation in place. The important part is preserving the current behavior, including the non-obvious parts:
- fallthrough-style behavior still needs to happen where it happens today
- logs, emitted events, updates, and alert levels must not change
- unknown event handling still needs to behave the same way

Expected `processEvent(eventType, data, deps)` result schema:
- Always returns `{ "originalType": <eventType>, "processed": <array of step names>, ... }`.
- Login/activity events may append update objects shaped like `{ "action": "last_active", "userId": <id> }` to `deps.updates`.
- Logout emits `session_end` with `{ "userId": <id> }`.
- Purchase events include `"purchase"` in `processed`.
- Warning/error events include `"alert"` in `processed`; `WARNING` returns `level: "low"` and `ERROR` returns `level: "high"`.
- Unknown events include `"unknown"` in `processed` and preserve `originalType`.

Start here:
- `/root/task/README.md`
- `/root/task/docs/release_notes.md`
- `/root/task/src/processEvent.js`
- `/root/task/src/sampleEventCatalog.js`

Save your edits under `/root/task`. Keep the current project layout, and do not replace the function with a stub.
