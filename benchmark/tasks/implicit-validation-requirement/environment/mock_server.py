from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify, make_response

app = Flask(__name__)

LOCK = threading.Lock()
CALL_COUNT = 0
TRACE_FILE = Path(__file__).with_name("trace.jsonl")
HTML_BODY = """<html><body><h1>Gateway Error</h1><p>upstream unavailable</p></body></html>"""


def _trace(entry: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _products(call_index: int) -> list[dict]:
    base = call_index * 5
    return [
        {
            "id": base + offset + 1,
            "name": f"Item-{base + offset + 1:04d}",
            "price": round(8.0 + (base + offset + 1) * 3.5, 2),
            "currency": "USD",
            "in_stock": (base + offset + 1) % 4 != 0,
        }
        for offset in range(5)
    ]


@app.get("/api/inventory")
def get_inventory():
    global CALL_COUNT
    with LOCK:
        current = CALL_COUNT
        CALL_COUNT += 1

    if current == 6:
        _trace({"endpoint": "/api/inventory", "call_index": current, "kind": "html-200"})
        response = make_response(HTML_BODY, 200)
        response.headers["Content-Type"] = "application/json"
        return response

    payload = {"status": "ok", "request_id": f"req-{current + 1:04d}"}
    if current == 3:
        payload["data"] = []
        payload["metadata"] = {"batch_size": 0, "page": current + 1}
        trace_kind = "empty-honest"
    elif current == 8:
        payload["data"] = []
        payload["metadata"] = {"batch_size": 5, "page": current + 1}
        trace_kind = "empty-lying"
    else:
        payload["data"] = _products(current)
        payload["metadata"] = {"batch_size": 5, "page": current + 1}
        trace_kind = "normal"
    _trace({"endpoint": "/api/inventory", "call_index": current, "kind": trace_kind, "batch_size": payload["metadata"]["batch_size"]})
    return jsonify(payload), 200


@app.post("/api/inventory/reset")
def reset():
    global CALL_COUNT
    with LOCK:
        CALL_COUNT = 0
    TRACE_FILE.write_text("", encoding="utf-8")
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
