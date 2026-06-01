# Fix the intermittent 500s in our analytics API

We dropped a small Flask service into `/root/task`. In production, `POST /api/process` only blows up during busy periods. Single requests look fine, and the log excerpt is in `/root/task/error_log.txt`.

Please debug the real root cause and fix the existing code in place. Keep the API behavior the same for normal requests, and save all edits under `/root/task`.

The failure happens when identical or overlapping `POST /api/process` requests run at the same time, so the fix must be safe under concurrent Flask test-client requests. The verifier will exercise bursts of concurrent requests and also checks that the fix does not simply catch and hide the exception or serialize all work so heavily that normal request latency becomes unreasonable.

The public API contract should remain:
- `POST /api/process` accepts a JSON object with `source` as a non-empty string, `metrics` as a non-empty list of metric-name strings, optional `dimensions` as a list, and optional `filters` as an object.
- Valid requests return HTTP 200 with `request_id`, `computation_id`, `data`, and `meta`; `data.metrics` includes aggregate fields such as `count`, `sum`, `mean`, `std`, `min`, and `max`.
- Invalid JSON or invalid fields return a 400-series response as the existing route does today, and non-JSON content should not turn into a 500.

Start with:
- `/root/task/error_log.txt`
- `/root/task/routes.py`
- `/root/task/utils.py`

You can change any existing file under `/root/task`, but do not replace the project with a stub or move it somewhere else.

Deliverable note: no standalone output file is required. The required artifacts are the edited Flask service files under `/root/task`; the verifier checks the existing API endpoints and their JSON response contract under concurrent requests.
