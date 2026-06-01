# Finish the webhook work in this repo

The FastAPI project is in `/root/task`. I was trying to finish the webhook endpoint, but the branch is messy right now: the local CI checks under `/root/task/ci_tests/` are currently failing, and the webhook route is still incomplete. Please work in place under `/root/task`, get the repo back into a healthy state, and finish the webhook implementation without breaking the existing app.

Expected behavior:
- Fix the existing CI failures rather than deleting or bypassing the checks in `/root/task/ci_tests/`.
- Keep the user API response shape from `UserResponseSchema.to_api_dict()` in `/root/task/app/models.py`: user objects include `id`, `display_name`, `username`, `email`, `role`, `is_active`, and `created_at`.
- `GET /users`, `GET /users/active`, and `GET /users/{user_id}` must continue to return JSON user data through the existing service layer.
- `POST /webhooks` must verify the `x-hub-signature-256` HMAC-SHA256 signature using `WEBHOOK_SECRET`, parse a JSON body, validate required fields `event_id`, `event_type`, and `data`, store a verified event, and return a JSON response containing the accepted `event_id`.
- Invalid signatures should return `403`; missing signatures and invalid JSON/payloads should return non-200 JSON errors.

Useful paths:
- `/root/task/app/routers/webhooks.py`
- `/root/task/ci_tests/`
- `/root/task/app/models.py`
- `/root/task/app/services.py`
- `/root/task/app/utils.py`

Save your changes in `/root/task`. Do not replace the app with a simplified stub.
