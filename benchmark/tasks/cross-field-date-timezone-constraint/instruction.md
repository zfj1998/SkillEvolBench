# Task: Validate Date Ranges Before Sending Search Requests

The search client in `/root/task` is letting some bad date ranges through.

Each request in `/root/task/queries.json` has a `start_date` and sometimes an `end_date`. The API contract says the range has to be valid after timezone normalization, not just when you compare the local clock text. Please fix the local validation so we catch invalid ranges before the outbound call.

Start here:
- `/root/task/README.md`
- `/root/task/search_client.py`
- `/root/task/queries.json`
- `/root/task/docs/timezone-migration.md`

What I need:
1. Validate `start_date` and `end_date` locally.
2. Handle timezone-aware comparisons correctly.
3. Use an explicit default timezone policy for naive timestamps that do not include an offset; the project docs define the default as UTC, and the validation report should make that normalization visible.
4. Reject ambiguous fall-back DST ranges where the two endpoints use different offsets for the same local date and repeated clock hour and the local end clock appears earlier than the local start clock. These ranges are not accepted even if a plain UTC instant comparison would otherwise put the end later.
5. Keep optional `end_date` optional.
6. Save the updated code under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Input and return contract:
- `queries.json` is an array of query objects. Each query has `start_date` and may have `end_date`; date strings are ISO 8601 values and may include timezone offsets.
- `process_queries(path)` returns a dictionary with `accepted`, `rejected`, and `trace`.
- Each rejected item includes zero-based `index`, `errors`, and the original query. Error objects should identify `param`, `error`, and the payload or normalized values used for the UTC comparison.
