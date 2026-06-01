Asynchronous report-generation workflow.

Relevant pieces:
- `request.json` contains the report month to submit.
- `report_client.py` wraps the POST / status / result API calls.
- `status_gate.py` decides whether polling can stop.
- `polling_policy.py` controls the wait interval between status checks.
- `mock_api.py` enforces both job readiness and a minimum polling interval.

Expected behavior:
- submit the job once
- poll `/status` until the response is truly `completed`
- wait long enough between polls
- fetch `/result` only after the task completes
- save the report to `report_output.json`
