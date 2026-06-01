# Fix the blank profile page by tracing the full failure path

The service code is in `/root/task`. Users can log in, but sometimes the profile page comes back blank instead of showing data or a real error. Please debug the actual chain of failures and fix the existing code in place.

Focus on the files under `/root/task`, keep the service behavior sensible for good requests, and save all edits there.

Expected API contract:
- `handle_request("POST", "/api/login", body={"username": ..., "password": ...})` returns `(200, {"token": <token>, "message": "Login successful"})` for valid credentials, `400` when either field is missing, and `401` for bad credentials.
- Authenticated profile requests use `Authorization: Bearer <token>`.
- `GET /api/profile` returns `(200, {"profile": <profile object>, "has_profile": True})` for the logged-in user.
- `GET /api/profile/<id>` returns the same profile envelope for existing users and `(404, {"error": "user not found"})` for nonexistent users.
- Database operational failures should propagate to an appropriate server-error response such as `500` or `503`; they must not be converted into `(200, {"profile": {}, "has_profile": False})`.
- Repeated or concurrent authenticated profile requests should return the same successful profile envelope, or the same appropriate non-200 error if an operational dependency fails. They must not intermittently produce blank-profile success responses such as `(200, {"profile": {}, "has_profile": False})`.
- Profile objects should include user-facing fields from the database, including `display_name` and `email`.

Good starting points:
- `/root/task/api_gateway.py`
- `/root/task/user_service.py`
- `/root/task/db_client.py`
- `/root/task/config.py`

Deliverable note: no standalone output file is required. The required artifacts are the edited service files under `/root/task`; the verifier checks the tuple/status-code API contract documented above.
