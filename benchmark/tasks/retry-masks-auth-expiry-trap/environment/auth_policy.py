from __future__ import annotations


def classify_response(response: dict) -> str:
    status = response["status"]
    body = response["body"]
    if status == 200:
        return "ok"
    if status == 401 and body.get("error") == "token_expired":
        # The starter still routes token-expired responses through the generic
        # retry lane instead of forcing a refresh-specific recovery path.
        return "retry"
    if status == 503:
        return "retry"
    return "fail"
