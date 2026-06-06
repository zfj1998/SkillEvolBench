from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SERVER = PROJECT / "mock_server.py"
CLIENT = PROJECT / "fetch_products.py"
OUTPUT = PROJECT / "output.json"


def _start_server():
    return subprocess.Popen([sys.executable, str(SERVER)], cwd=PROJECT)


def _reset():
    import requests

    for _ in range(20):
        try:
            if requests.post("http://localhost:5050/api/products/reset", timeout=1).status_code == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("reset failed")


def _run_client():
    server = _start_server()
    time.sleep(1.0)
    try:
        _reset()
        result = subprocess.run([sys.executable, str(CLIENT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
        output = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else []
        return result, output
    finally:
        server.terminate()
        server.wait(timeout=5)


def _by_id():
    return {item["id"]: item for item in _run_client()[1]}


def run():
    public = run_checks("public", [
        ("twenty_rows_written", lambda: len(_run_client()[1]) == 20 or (_ for _ in ()).throw(AssertionError("expected 20 records"))),
        ("no_missing_schema", lambda: all({"id", "name", "price", "currency", "in_stock", "updated_at"} <= set(item) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("missing fields in output"))),
    ])
    hidden = run_checks("hidden", [
        ("no_negative_prices", lambda: all(item["price"] >= 0 for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("negative prices remain"))),
        ("fallback_only_for_bad_records", lambda: (_by_id()[4]["updated_at"] == "2026-04-11T10:00:00Z" and _by_id()[8]["updated_at"] == "2026-04-11T10:00:00Z" and _by_id()[1]["updated_at"] == "2026-04-12T10:00:00Z") or (_ for _ in ()).throw(AssertionError("replacement provenance incorrect"))),
        ("null_and_missing_names_replaced", lambda: isinstance(_by_id()[8]["name"], str) and isinstance(_by_id()[15]["name"], str) or (_ for _ in ()).throw(AssertionError("name anomalies not repaired"))),
        ("no_crash", lambda: _run_client()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("client exited non-zero"))),
    ])
    return emit_report("E2-LS5-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
