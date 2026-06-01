from .audit import prepare_payload, record_validation_attempt
from .shared import bad_request, ok


def create_order(payload):
    context = prepare_payload(payload, "create_order")
    payload = context["payload"]
    record_validation_attempt("create_order", payload)
    if "user_id" not in payload:
        return bad_request("user_id", "user_id is required")
    if "product_ids" not in payload:
        return bad_request("product_ids", "product_ids is required")
    if "quantity" not in payload:
        return bad_request("quantity", "quantity is required")
    if not isinstance(payload["user_id"], int):
        return bad_request("user_id", "user_id must be an integer")
    if not isinstance(payload["product_ids"], list):
        return bad_request("product_ids", "product_ids must be a list")
    if not payload["product_ids"]:
        return bad_request("product_ids", "product_ids cannot be empty")
    if not isinstance(payload["quantity"], int):
        return bad_request("quantity", "quantity must be an integer")
    if payload["quantity"] < 1 or payload["quantity"] > 100:
        return bad_request("quantity", "quantity must be between 1 and 100")
    return ok({"kind": "order", "payload": payload})
