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


def run():
    public = run_checks("public", [
        ("output_exists", lambda: _run_client()[1] or (_ for _ in ()).throw(AssertionError("missing output"))),
        ("uniform_objects", lambda: all(isinstance(item, dict) for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("output format invalid"))),
    ])
    hidden = run_checks("hidden", [
        ("all_50_current_records", lambda: (len(_run_client()[1]) == 50 and all(item["id"] < 9000 for item in _run_client()[1])) or (_ for _ in ()).throw(AssertionError("expected 50 current records with no stale extras"))),
        ("v1_and_v2_prices_correct", lambda: all(abs(item["price"] - round(9.5 + item["id"] * 2.25, 2)) < 1e-9 for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("stale prices detected"))),
        ("no_discontinued_records", lambda: not any(item["name"].startswith("Discontinued-") for item in _run_client()[1]) or (_ for _ in ()).throw(AssertionError("discontinued products leaked into output"))),
        ("no_crash", lambda: _run_client()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("client exited non-zero"))),
    ])
    return emit_report("E2-LS5-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
