from __future__ import annotations

from copy import deepcopy
from typing import Any


class OrderAPI:
    def __init__(self):
        self.orders: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []
        self.orders_by_key: dict[str, dict[str, Any]] = {}
        self.next_order_id = 1
        self.first_request_timed_out = False

    def create_order(self, body: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        headers = dict(headers or {})
        key = headers.get("Idempotency-Key")
        self.trace.append({"headers": deepcopy(headers), "body": deepcopy(body)})
        if key and key in self.orders_by_key:
            return {"status": 200, "body": {"order": deepcopy(self.orders_by_key[key]), "replayed": True}}
        order = {
            "order_id": f"ord-{self.next_order_id}",
            "sku": body["sku"],
            "quantity": body["quantity"],
        }
        self.next_order_id += 1
        self.orders.append(order)
        if key:
            self.orders_by_key[key] = order
        if not self.first_request_timed_out:
            self.first_request_timed_out = True
            raise TimeoutError("request timed out after the order was created")
        return {"status": 201, "body": {"order": deepcopy(order), "replayed": False}}
