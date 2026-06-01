# Task: Stop Depending on Backend 400 Payloads

The request processor in `/root/task` currently behaves like the backend error format is stable forever, and I do not want that dependency.

Please fix the client so invalid requests are rejected locally before they hit the backend. We still need good error reporting, but it should come from our own validation layer rather than whatever 400 body the server happens to return.

Start here:
- `/root/task/README.md`
- `/root/task/client.py`
- `/root/task/requests.json`
- `/root/task/docs/backend-upgrade.md`

What I need:
1. Validate requests locally before sending them.
2. Keep a stable client-side error format.
3. Make sure backend 400 payload shape changes do not break the flow.
4. Save the updated files under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- `process_requests(path)` must return a dictionary with `successes`, `failures`, and `trace`.
- Each failure must be produced by local validation and use the stable client-side error schema from `/root/task/error_presenter.py`: `field`, `message`, and `source`.
- Invalid rows must not be sent to the backend; backend 400 response bodies are not part of the client contract.
