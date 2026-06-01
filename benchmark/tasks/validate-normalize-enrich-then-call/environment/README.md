# Environment Plan: E2-LS1-T6

Role: `composition`
Gap focus: `Composition of pre-call validation with profile-based enrichment and fallback.`

Scenario:
Transaction requests may arrive without timezone or currency. The client must validate required fields, query a profile API to fill missing data, fall back when the profile is incomplete or missing, normalize values into UTC and USD, and only then call the transaction API.

Environment files:
- `transactions.py`
- `requests.json`
- `mock_profile_api.py`
- `mock_transaction_api.py`
- `public_tests/test_transactions.py`

Key design notes:
At least three user profiles should exist: one complete, one with `timezone = null`, and one that returns 404. Hidden checks should verify both enrichment and fallback behavior before the final call.

Public checks:
- Requests for complete profiles succeed.
- Final outbound payloads follow the target API format.

Hidden checks:
- Timezone is filled from profile data when available.
- Null profile timezone falls back to UTC.
- Missing profile falls back to system defaults.
- EUR inputs are normalized into USD before the final call.
- The final parameters satisfy the target API contract.

Process checks:
- The pipeline order is validate -> enrich -> normalize -> call.
- Null profile fields trigger fallback logic.
- 404 profile lookups also trigger fallback logic.
