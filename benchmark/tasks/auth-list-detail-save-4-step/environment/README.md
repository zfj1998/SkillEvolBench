Protected item export workflow.

Relevant pieces:
- `credentials.json` contains the local worker credentials.
- `auth_session.py` builds the session/auth headers that should flow into every downstream call.
- `detail_collector.py` owns the fan-out from list results to detail requests.
- `request_budget.py` is supposed to keep the detail stage under the API's 3-per-second limit.
- `mock_api.py` simulates the protected endpoints and records a full trace.

Expected behavior:
- authenticate once
- reuse the same bearer token for `/items` and every `/items/{id}` call
- retrieve all 5 detail rows
- write the final export to `output.json`
