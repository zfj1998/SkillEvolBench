# Task: Generate the Report Through the Async Job API

The worker in `/root/task` needs to generate the monthly report through the async API flow:
1. submit the report request,
2. poll job status until it is really complete,
3. only then fetch the final result,
4. save the report to `/root/task/report_output.json`.

The starter has already been broken into helpers, but the readiness gate still treats an in-progress task as if it were safe to read.

Start here:
- `/root/task/README.md`
- `/root/task/report_workflow.py`
- `/root/task/report_client.py`
- `/root/task/status_gate.py`
- `/root/task/polling_policy.py`
- `/root/task/mock_api.py`
- `/root/task/request.json`

What I need:
1. Use the POST → poll status → GET result async pattern.
2. Wait between polls so the status endpoint is not hammered.
3. Fetch the result only after the task is completed.
4. Save the final report to `/root/task/report_output.json`.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `/root/task/report_output.json` as the final report payload from the completed job's `report` field, not the polling envelope.
- The JSON root must be `{ "month": string, "totals": { "new_signups": number, "revenue": number }, "segments": string[] }`.
- The observable flow should be POST report request, poll status with waits between polls, then GET the result.
