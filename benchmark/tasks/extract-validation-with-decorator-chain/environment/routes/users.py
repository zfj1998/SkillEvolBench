from .audit import prepare_payload, record_validation_attempt
from .shared import EMAIL_RE, bad_request, ok


def create_user(payload):
    context = prepare_payload(payload, "create_user")
    payload = context["payload"]
    record_validation_attempt("create_user", payload)
    if "name" not in payload or not payload["name"]:
        return bad_request("name", "name is required")
    if "email" not in payload or not payload["email"]:
        return bad_request("email", "email is required")
    if not isinstance(payload["name"], str):
        return bad_request("name", "name must be a string")
    if not isinstance(payload["email"], str):
        return bad_request("email", "email must be a string")
    if not EMAIL_RE.match(payload["email"]):
        return bad_request("email", "email format is invalid")
    if "age" in payload and payload["age"] is not None:
        if not isinstance(payload["age"], int):
            return bad_request("age", "age must be an integer")
        if payload["age"] < 0 or payload["age"] > 150:
            return bad_request("age", "age must be between 0 and 150")
    return ok({"kind": "user", "payload": payload})
