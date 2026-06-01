# Environment Plan: E2-LS1-T5

Role: `adversarial`
Gap focus: `Trap: the server's 400s look good enough until the format changes.`

Scenario:
The mock API returns friendly 400 payloads for invalid input. A lazy implementation may just forward those bodies. Hidden tests swap the 400 schema, so only local interception is robust.

Environment files:
- `client.py`
- `requests.json`
- `mock_api_v1/app.py`
- `mock_api_v2/app.py`
- `public_tests/test_client.py`

Key design notes:
Version one of the server should return a flat `{error, field}` body. Hidden tests should switch to a nested `{errors: [...]}` body. The correct trace contains zero 400 responses because invalid requests never leave the client.

Public checks:
- Valid requests succeed.
- Invalid requests produce error reports.

Hidden checks:
- Trace contains zero 400 responses.
- The implementation does not crash when the remote error schema changes.
- Reported errors use the client's own stable schema rather than forwarding server bodies.

Process checks:
- Validation happens before the network call.
- The code does not parse remote 400 payloads as its primary validation path.
- Error objects are locally generated.
