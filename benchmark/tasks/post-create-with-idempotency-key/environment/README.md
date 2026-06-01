# Environment Plan: E2-LS2-T3

Role: `variant`
Gap focus: `Gap 2: POST retries must preserve idempotency, not just retry blindly.`

Scenario:
The order creation API can time out after the server has already created the order. The client must retry safely by reusing a shared idempotency identity across attempts.

Starter files:
- `order_client.py`
- `mock_api.py`
- `docs/idempotency-notes.md`

Key design notes:
The first request times out after the order is committed. If the retry path builds a fresh idempotency context, the environment will create a duplicate order.
