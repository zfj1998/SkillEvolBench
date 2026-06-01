# Environment Plan: E2-LS1-T1

Role: `canonical`
Gap focus: `No gap exposure; v0 validation logic should work.`

Scenario:
A batch of ten weather requests mixes valid inputs with empty strings, wrong types, out-of-range values, bad enums, and one request containing two simultaneous mistakes.

Environment files:
- `client.py`
- `requests.json`
- `mock_api.py`
- `public_tests/test_client.py`

Key design notes:
The mock API should expose `GET /weather?city=&days=&units=`. Exactly four requests should be valid, including boundary values `days=1` and `days=14`. One invalid request should contain two separate validation failures.

Public checks:
- Exactly four requests are sent to the API.
- Valid cities appear in the final results.
- Errors include both the parameter name and an explanation.

Hidden checks:
- Errors include the bad value and the expected contract.
- The double-fault request reports both failures.
- All invalid request reports use one consistent structure.
- No HTTP 400 responses appear in the trace because invalid items are blocked locally.
- Boundary values `days=1` and `days=14` are allowed.

Process checks:
- Validation happens before each outbound call.
- Error objects include `param`, `error`, `value`, and `expected` fields.
- The implementation does not rely on catching remote 400 responses as validation.
