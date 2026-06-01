from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

CALL_COUNT = 0
LOCK = threading.Lock()
TRACE_FILE = Path(__file__).with_name("trace.jsonl")

ANOMALY_CALLS = {3, 7}


def _write_trace(entry: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _batch(call_index: int) -> list[dict]:
    base = call_index * 5
    return [
        {
            "id": base + offset + 1,
            "name": f"Product-{base + offset + 1:03d}",
            "price": round(11.5 + (base + offset + 1) * 1.75, 2),
            "currency": "USD",
            "in_stock": (base + offset + 1) % 4 != 0,
            "batch": call_index + 1,
        }
        for offset in range(5)
    ]


@app.get("/api/products")
def get_products():
    global CALL_COUNT
    with LOCK:
        current = CALL_COUNT
        CALL_COUNT += 1

    envelope = {
        "status": "ok",
        "request_id": f"req-{current + 1:04d}",
        "data_status": "ready",
        "snapshot_token": f"snap-{current + 1:04d}",
        "metadata": {"page": current + 1, "batch_size": 5},
    }

    if current in ANOMALY_CALLS:
        envelope["maintenance_window"] = True
        envelope["message"] = "feed temporarily unavailable"
    else:
        envelope["data"] = _batch(current)

    _write_trace(
        {
            "endpoint": "/api/products",
            "call_index": current,
            "has_data": "data" in envelope,
            "status_code": 200,
            "query": dict(request.args),
        }
    )
    return jsonify(envelope), 200


@app.post("/api/products/reset")
def reset():
    global CALL_COUNT
    with LOCK:
        CALL_COUNT = 0
    TRACE_FILE.write_text("", encoding="utf-8")
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
