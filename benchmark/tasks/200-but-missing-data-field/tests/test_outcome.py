from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
OUTPUT = PROJECT / "output.json"
TRACE = PROJECT / "trace.jsonl"
LOG = PROJECT / "fetch_products.log"
SERVER = PROJECT / "mock_server.py"
CLIENT = PROJECT / "fetch_products.py"
EXPECTED_IDS = {idx for idx in range(1, 51) if idx not in set(range(16, 21)) | set(range(36, 41))}


def _start_server():
    return subprocess.Popen([sys.executable, str(SERVER)], cwd=PROJECT)


def _reset_server():
    import requests

    for _ in range(20):
        try:
            response = requests.post("http://localhost:5050/api/products/reset", timeout=1)
            if response.status_code == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("failed to reset mock server")


def _run_client():
    if OUTPUT.exists():
        OUTPUT.unlink()
    server = _start_server()
    time.sleep(1.2)
    try:
        _reset_server()
        result = subprocess.run([sys.executable, str(CLIENT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
        payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else []
        trace = [json.loads(line) for line in TRACE.read_text(encoding="utf-8").splitlines() if line.strip()] if TRACE.exists() else []
        log_text = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
        return result, payload, trace, log_text
    finally:
        server.terminate()
        server.wait(timeout=5)


def run():
    public = run_checks("public", [
        ("output_exists", lambda: _run_client()[1] or (_ for _ in ()).throw(AssertionError("output.json missing or empty"))),
        ("output_format", lambda: all(isinstance(item, dict) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("output should be a list of objects"))),
    ])
    hidden = run_checks("hidden", [
        ("no_crash", lambda: _run_client()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("client exited non-zero"))),
        ("exact_unique_valid_records", lambda: ({item["id"] for item in _run_client()[1]} == EXPECTED_IDS and len(_run_client()[1]) == 40) or (_ for _ in ()).throw(AssertionError("expected 40 unique valid records"))),
        ("product_schema_complete", lambda: all({"id", "name", "price", "currency", "in_stock", "batch"} <= set(item) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("product rows missing required catalog fields"))),
        ("missing_data_logged", lambda: "missing data" in _run_client()[3].lower() or (_ for _ in ()).throw(AssertionError("missing-data anomaly not logged"))),
        ("no_duplicate_replay", lambda: len({item["id"] for item in _run_client()[1]}) == len(_run_client()[1]) or (_ for _ in ()).throw(AssertionError("duplicate records found"))),
    ])
    return emit_report("E2-LS5-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
