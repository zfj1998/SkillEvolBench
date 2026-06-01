The create-order endpoint supports `Idempotency-Key`.

If a timeout happens after the order is committed, the client must retry with the same idempotency identity. A new key on retry is treated as a brand-new order request.
