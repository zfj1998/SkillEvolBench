from __future__ import annotations

from idempotency_context import build_idempotency_key


def build_create_request(body: dict) -> tuple[dict, dict]:
    headers = {"Idempotency-Key": build_idempotency_key()}
    payload = dict(body)
    return headers, payload
