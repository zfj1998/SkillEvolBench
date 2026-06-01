from .audit import prepare_payload, record_validation_attempt
from .shared import bad_request, ok


def create_review(payload):
    context = prepare_payload(payload, "create_review")
    payload = context["payload"]
    record_validation_attempt("create_review", payload)
    if "user_id" not in payload:
        return bad_request("user_id", "user_id is required")
    if "product_id" not in payload:
        return bad_request("product_id", "product_id is required")
    if "rating" not in payload:
        return bad_request("rating", "rating is required")
    if not isinstance(payload["user_id"], int):
        return bad_request("user_id", "user_id must be an integer")
    if not isinstance(payload["product_id"], int):
        return bad_request("product_id", "product_id must be an integer")
    if not isinstance(payload["rating"], int):
        return bad_request("rating", "rating must be an integer")
    if payload["rating"] < 1 or payload["rating"] > 5:
        return bad_request("rating", "rating must be between 1 and 5")
    if "comment" in payload and payload["comment"] is not None:
        if not isinstance(payload["comment"], str):
            return bad_request("comment", "comment must be a string")
        if len(payload["comment"]) > 1000:
            return bad_request("comment", "comment is too long")
    return ok({"kind": "review", "payload": payload})
