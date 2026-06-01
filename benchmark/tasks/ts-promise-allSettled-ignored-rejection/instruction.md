# Fix the report job so timeouts are not silently treated as real zeros

The TypeScript job lives in `/root/task`. Product flagged that the monthly report sometimes finishes with exit code `0`, but a couple of sections quietly turn into misleading zero values when upstream calls time out.

Please fix the root cause in the existing code under `/root/task`. Keep the report shape usable, but make failed sources show up as failures instead of looking like healthy zero-data sections. Save all edits under `/root/task`.

The CLI entry point is `/root/task/src/index.ts`. It accepts `--period`, `--timeout`, and `--output`; the output path must be written as JSON even when one or more upstream sources fail or time out.

Expected report schema:
- Top level object: `{ "title": <string>, "sections": [...], "meta": {...} }`.
- `sections` must contain one entry for each source in `/root/task/src/types.ts`: `user_stats`, `orders`, `inventory`, `reviews`, and `traffic`.
- Each section has `source`, `label`, `value`, `display_value`, `unit`, `breakdown`, `status`, `provenance`, `notes`, and `collected_at`.
- Successfully fulfilled sources keep `status: "ok"` and their live values.
- Timed-out or rejected sources must not be represented as healthy zero-data sections; they should have a non-`ok` status such as `"error"` or `"unavailable"` and include failure metadata through `meta.recoverable_failures`, `meta.failure_log`, section `notes`, or stderr logging.

Start with:
- `/root/task/src/reportGenerator.ts`
- `/root/task/src/formatter.ts`
- `/root/task/src/apiClient.ts`
