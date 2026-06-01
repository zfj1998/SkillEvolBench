# Task: Authenticate, Collect Item Details, and Save the Full Export

The worker in `/root/task` is supposed to do a full protected-data pull:
1. authenticate,
2. list the item ids,
3. fetch every item detail with the same bearer token,
4. save the final rows to `/root/task/output.json`.

Right now the starter looks organized, but the orchestration around auth/session reuse and detail pacing is still off, so the workflow does not reliably complete.

Start here:
- `/root/task/README.md`
- `/root/task/workflow.py`
- `/root/task/auth_session.py`
- `/root/task/detail_collector.py`
- `/root/task/request_budget.py`
- `/root/task/mock_api.py`
- `/root/task/credentials.json`

What I need:
1. Keep the 4-step auth → list → detail → save pipeline intact.
2. Propagate the bearer token through every downstream request.
3. Fetch all 5 detail records without hitting the detail rate limit.
4. Save the final full payload to `/root/task/output.json`.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `/root/task/output.json` as an array of 5 item detail objects. Each row must include `id`, `name`, `category`, `score`, and `source`.
- Use the bearer token from auth for list and detail calls. Pace detail requests so the 3-per-second detail limit is not exceeded.
