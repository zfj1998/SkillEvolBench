# Task: Retry the Order Create Call Without Duplicating Orders

The order client in `/root/task` is not safe under timeout conditions.

The create-order API supports an `Idempotency-Key` header. The first request can time out even though the server already created the order, so a blind retry can create a duplicate. Please make the client safe for that case.

Start here:
- `/root/task/README.md`
- `/root/task/order_client.py`
- `/root/task/mock_api.py`
- `/root/task/docs/idempotency-notes.md`

What I need:
1. Create the order successfully even when the first response times out.
2. Reuse the same idempotency key across retries.
3. Keep the request body stable across attempts.
4. Save the updated implementation under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Idempotency contract:
- Generate one UUID idempotency key for the logical order creation attempt.
- Reuse that same UUID key and the same request body for every retry of that logical create operation.
- Keep retry attempts bounded by the existing `max_attempts` parameter.
- Return the created order object from the API response.

Request/response schema: call `api.create_order(body, headers={"Idempotency-Key": "<uuid>"})` with the original order body object, and return the nested `response["body"]["order"]` object containing `order_id`, `sku`, and `quantity`.
