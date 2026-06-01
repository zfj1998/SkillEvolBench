from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify

app = Flask(__name__)

LOCK = threading.Lock()
CALL_COUNT = 0
TRACE_FILE = Path(__file__).with_name("trace.jsonl")
PRICE_OVERRIDES = {7: -0.01, 8: 0.00, 14: -50.00}
DISCOUNT_IDS = {3, 7, 11, 14, 18}


def _trace(entry: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _batch(call_index: int) -> list[dict]:
    base = call_index * 5
    records = []
    for offset in range(5):
        pid = base + offset + 1
        record = {
            "id": pid,
            "name": f"SKU-{pid:04d}",
            "price": PRICE_OVERRIDES.get(pid, round(15.0 + pid * 7.5 + (pid % 4) * 3.25, 2)),
            "currency": "USD",
            "in_stock": pid % 5 != 0,
        }
        if pid in DISCOUNT_IDS:
            record["discount_applied"] = True
        records.append(record)
    return records


@app.get("/api/pricing")
def get_pricing():
    global CALL_COUNT
    with LOCK:
        current = CALL_COUNT
        CALL_COUNT += 1
    payload = {
        "status": "ok",
        "metadata": {"batch": current + 1, "pricing_engine_validated": True},
        "data": _batch(current),
    }
    _trace({"endpoint": "/api/pricing", "call_index": current, "count": len(payload["data"])})
    return jsonify(payload), 200


@app.post("/api/pricing/reset")
def reset():
    global CALL_COUNT
    with LOCK:
        CALL_COUNT = 0
    TRACE_FILE.write_text("", encoding="utf-8")
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
