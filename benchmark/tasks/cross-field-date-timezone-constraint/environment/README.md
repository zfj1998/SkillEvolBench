# Environment Plan: E2-LS1-T2

Role: `enriched`
Gap focus: `Gap 1: cross-parameter constraints under timezone normalization.`

Scenario:
Eight search requests include same-timezone cases, an obvious invalid range, a hidden cross-timezone trap, a missing timezone case, an equality boundary, and a missing optional end date.

Environment files:
- `search_client.py`
- `queries.json`
- `mock_api/app.py`
- `public_tests/test_search_client.py`

Key design notes:
The key trap should look valid when comparing local clock times but become invalid once both datetimes are converted to UTC. One request should omit timezone metadata so the solver must choose and document a default policy.

Public checks:
- Clearly valid requests are sent.
- Clearly invalid requests are blocked.

Hidden checks:
- The cross-timezone trap is rejected after UTC normalization.
- Equal start and end timestamps are accepted.
- A request with missing optional `end_date` is accepted.
- The missing-timezone case is handled consistently with a documented default.
- Error reporting references the UTC comparison or normalized values.

Process checks:
- The implementation uses a real datetime parser or timezone library.
- Comparison happens on normalized UTC values rather than raw strings.
- The missing-timezone policy is explicit.
