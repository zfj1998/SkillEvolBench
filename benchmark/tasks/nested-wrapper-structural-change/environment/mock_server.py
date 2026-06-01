from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify

app = Flask(__name__)

LOCK = threading.Lock()
CALL_COUNT = 0
TRACE_FILE = Path(__file__).with_name("trace.jsonl")
V2_CALLS = {5, 6, 7, 8, 9}


def _trace(entry: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _current_products(call_index: int) -> list[dict]:
    base = call_index * 5
    return [
        {
            "id": base + offset + 1,
            "name": f"Product-{base + offset + 1:03d}",
            "price": round(9.5 + (base + offset + 1) * 2.25, 2),
            "currency": "USD",
            "in_stock": (base + offset + 1) % 3 != 0,
        }
        for offset in range(5)
    ]


def _stale_products(call_index: int) -> list[dict]:
    products = _current_products(call_index)
    stale = []
    for index, item in enumerate(products):
        record = dict(item)
        if index in {1, 3}:
            record["price"] = round(record["price"] * 0.94, 2)
        stale.append(record)
    stale.append(
        {
            "id": 9000 + call_index,
            "name": f"Discontinued-{9000 + call_index}",
            "price": 0.99,
            "currency": "USD",
            "in_stock": False,
        }
    )
    return stale


@app.get("/api/products")
def get_products():
    global CALL_COUNT
    with LOCK:
        current = CALL_COUNT
        CALL_COUNT += 1

    payload = {
        "status": "ok",
        "request_id": f"req-{current + 1:04d}",
        "api_version": "2.1" if current in V2_CALLS else "1.9",
    }

    if current in V2_CALLS:
        payload["result"] = {
            "items": _current_products(current),
            "meta": {"page": current + 1, "rollout": "canary"},
        }
        payload["data"] = _stale_products(current)
        payload["data_contract"] = "transitional"
    else:
        payload["data"] = _current_products(current)

    _trace(
        {
            "endpoint": "/api/products",
            "call_index": current,
            "api_version": payload["api_version"],
            "has_result": "result" in payload,
            "data_len": len(payload.get("data", [])) if isinstance(payload.get("data"), list) else None,
        }
    )
    return jsonify(payload), 200


@app.post("/api/products/reset")
def reset():
    global CALL_COUNT
    with LOCK:
        CALL_COUNT = 0
    TRACE_FILE.write_text("", encoding="utf-8")
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
