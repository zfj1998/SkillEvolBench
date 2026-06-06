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
            if requests.post("http://localhost:5050/api/inventory/reset", timeout=1).status_code == 200:
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


def run():
    public = run_checks("public", [
        ("output_exists", lambda: _run_client()[1] is not None or (_ for _ in ()).throw(AssertionError("missing output"))),
        ("output_format", lambda: isinstance(_run_client()[1], list) or (_ for _ in ()).throw(AssertionError("output should be a list"))),
    ])
    hidden = run_checks("hidden", [
        ("html_not_saved", lambda: all(isinstance(item, dict) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("non-json garbage leaked into output"))),
        ("only_valid_inventory_rows", lambda: len({item["id"] for item in _run_client()[1]}) == 35 and len(_run_client()[1]) == 35 or (_ for _ in ()).throw(AssertionError("expected 35 unique valid rows"))),
        ("inventory_schema_complete", lambda: all({"id", "name", "price", "currency", "in_stock"} <= set(item) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("inventory rows missing required fields"))),
        ("no_crash", lambda: _run_client()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("client exited non-zero"))),
        ("no_duplicate_replay", lambda: len({item["id"] for item in _run_client()[1]}) == len(_run_client()[1]) or (_ for _ in ()).throw(AssertionError("duplicate replay detected"))),
    ])
    return emit_report("E2-LS5-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
