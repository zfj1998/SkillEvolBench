from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify

app = Flask(__name__)

LOCK = threading.Lock()
CALL_COUNT = 0
TRACE_FILE = Path(__file__).with_name("trace.jsonl")
PRIMARY_DATE = "2026-04-12T10:00:00Z"
BACKUP_DATE = "2026-04-11T10:00:00Z"
NEGATIVE_IDS = {4: -5.00, 11: -12.50, 17: -0.01}
ABSENT_NAME_IDS = {8}
NULL_NAME_IDS = {15}


def _trace(entry: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _primary_product(pid: int) -> dict:
    record = {
        "id": pid,
        "price": NEGATIVE_IDS.get(pid, round(10.0 + pid * 3.0, 2)),
        "currency": "USD",
        "in_stock": pid % 4 != 0,
        "updated_at": PRIMARY_DATE,
    }
    if pid in ABSENT_NAME_IDS:
        return record
    if pid in NULL_NAME_IDS:
        record["name"] = None
        return record
    record["name"] = f"Product-{pid:03d}"
    return record


def _backup_product(pid: int) -> dict:
    return {
        "id": pid,
        "name": f"Product-{pid:03d}",
        "price": round(10.0 + pid * 3.0, 2),
        "currency": "USD",
        "in_stock": pid % 4 != 0,
        "updated_at": BACKUP_DATE,
    }


@app.get("/api/products")
def get_products():
    global CALL_COUNT
    with LOCK:
        current = CALL_COUNT
        CALL_COUNT += 1
    start = current * 5 + 1
    ids = list(range(start, start + 5))
    _trace({"endpoint": "/api/products", "ids": ids, "call_index": current})
    return jsonify({"status": "ok", "data": [_primary_product(pid) for pid in ids]}), 200


@app.get("/api/products/backup/<int:product_id>")
def get_backup(product_id: int):
    _trace({"endpoint": "/api/products/backup", "product_id": product_id})
    return jsonify({"status": "ok", "data": _backup_product(product_id)}), 200


@app.post("/api/products/reset")
def reset():
    global CALL_COUNT
    with LOCK:
        CALL_COUNT = 0
    TRACE_FILE.write_text("", encoding="utf-8")
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
