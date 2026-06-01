# Task: Complete the Validation and Enrichment Pipeline Before Calling Transactions

The transaction flow in `/root/task` is missing some important pre-call steps.

Each request may arrive without all the fields the final transaction API needs. Before we call the target API, we need to validate the input, enrich missing values from the profile API, apply fallback rules when profile data is incomplete, normalize the outbound payload, and only then send it.

Start here:
- `/root/task/README.md`
- `/root/task/transactions.py`
- `/root/task/requests.json`
- `/root/task/docs/profile-sync.md`

What I need:
1. Validate each request before any API call.
2. Enrich missing fields from the profile service when possible.
3. Apply fallbacks when profile data is null or missing.
4. Normalize the final outbound payload and save the changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Outbound payload contract:
- Every transaction sent to the target API must include `user_id`, `amount`, `currency`, and `timezone`.
- Validate required input fields before calling either the profile API or the transaction API. Missing required fields should fail locally.
- The final outbound `currency` must be `USD`; missing or null timezone values must fall back to `UTC`.
- `process_transactions(path)` should return a dictionary containing the API results and traces for profile and transaction calls.
