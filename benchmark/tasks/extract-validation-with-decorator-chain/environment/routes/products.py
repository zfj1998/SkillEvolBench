from .audit import prepare_payload, record_validation_attempt
from .shared import ALLOWED_CATEGORIES, bad_request, ok


def create_product(payload):
    context = prepare_payload(payload, "create_product")
    payload = context["payload"]
    record_validation_attempt("create_product", payload)
    if "title" not in payload or not payload["title"]:
        return bad_request("title", "title is required")
    if "price" not in payload:
        return bad_request("price", "price is required")
    if "category" not in payload or not payload["category"]:
        return bad_request("category", "category is required")
    if not isinstance(payload["title"], str):
        return bad_request("title", "title must be a string")
    if not isinstance(payload["price"], (int, float)):
        return bad_request("price", "price must be numeric")
    if payload["price"] <= 0:
        return bad_request("price", "price must be greater than zero")
    if not isinstance(payload["category"], str):
        return bad_request("category", "category must be a string")
    if payload["category"] not in ALLOWED_CATEGORIES:
        return bad_request("category", "category is invalid")
    return ok({"kind": "product", "payload": payload})
