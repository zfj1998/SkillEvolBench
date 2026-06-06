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
LOG = PROJECT / "fetch_products.log"


def _start_server():
    return subprocess.Popen([sys.executable, str(SERVER)], cwd=PROJECT)


def _reset():
    import requests

    for _ in range(20):
        try:
            if requests.post("http://localhost:5050/api/pricing/reset", timeout=1).status_code == 200:
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
        log_text = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
        return result, output, log_text
    finally:
        server.terminate()
        server.wait(timeout=5)


def run():
    public = run_checks("public", [
        ("output_exists", lambda: _run_client()[1] or (_ for _ in ()).throw(AssertionError("missing output"))),
        ("output_format", lambda: all(isinstance(item, dict) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("output format invalid"))),
    ])
    hidden = run_checks("hidden", [
        ("only_18_valid_records", lambda: len(_run_client()[1]) == 18 or (_ for _ in ()).throw(AssertionError("expected 18 valid records"))),
        ("pricing_schema_complete", lambda: all({"id", "name", "price", "currency", "in_stock"} <= set(item) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("pricing rows missing required fields"))),
        ("optional_discount_preserved", lambda: any(item.get("id") == 3 and item.get("discount_applied") is True for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("optional discount_applied field should be preserved when present"))),
        ("negative_prices_removed", lambda: all(item["price"] >= 0 for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("negative prices leaked"))),
        ("free_sample_retained", lambda: any(item["id"] == 8 and item["price"] == 0.0 for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("free sample missing"))),
        ("anomalies_logged", lambda: "negative price" in _run_client()[2].lower() or (_ for _ in ()).throw(AssertionError("negative-price anomaly not logged"))),
    ])
    return emit_report("E2-LS5-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
