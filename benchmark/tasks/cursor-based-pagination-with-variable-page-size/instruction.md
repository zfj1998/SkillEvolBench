# Task: Fix the Event Stream Pagination Client

The worker under `/root/task` needs to pull the full event stream and save it to `output.json`.

This API does not use offset pagination. It returns an opaque `next_cursor`, and the number of events per page can change from request to request. The current client still carries assumptions from the older fixed-window collector.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/cursor_contract.py`
- `/root/task/cursor_checkpoint.py`
- `/root/task/mock_api.py`
- `/root/task/docs/event-stream-api.md`

What I need:
1. Retrieve all events from the stream.
2. Use the API-provided cursor chain correctly.
3. Do not assume a fixed page size.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of event objects. Each event has integer `id` and event payload fields from the API. The provided stream contains exactly 80 unique events.
- Write `trace.json` as an object with a `trace` array recording each request cursor, request params, returned `next_cursor`, and returned ids.
- Stop only when the API returns a null `next_cursor`.
