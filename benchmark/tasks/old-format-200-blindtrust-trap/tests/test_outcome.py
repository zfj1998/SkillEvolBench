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
CLIENT = PROJECT / "fetch_users.py"
OUTPUT = PROJECT / "output.json"


def _start_server():
    return subprocess.Popen([sys.executable, str(SERVER)], cwd=PROJECT)


def _reset():
    import requests

    for _ in range(20):
        try:
            if requests.post("http://localhost:5050/api/users/reset", timeout=1).status_code == 200:
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
        ("output_exists", lambda: _run_client()[1] or (_ for _ in ()).throw(AssertionError("missing output"))),
        ("ten_users_exported", lambda: len(_run_client()[1]) == 10 or (_ for _ in ()).throw(AssertionError("expected 10 users"))),
    ])
    hidden = run_checks("hidden", [
        ("uses_new_name", lambda: _by_id()[1]["username"] == "Alice Smith" or (_ for _ in ()).throw(AssertionError("stale username selected"))),
        ("uses_new_phone", lambda: _by_id()[2]["phone"] == "+1-555-0203" or (_ for _ in ()).throw(AssertionError("stale phone selected"))),
        ("uses_new_email", lambda: _by_id()[7]["email"] == "george.wilson@company.com" or (_ for _ in ()).throw(AssertionError("stale email selected"))),
        ("no_crash", lambda: _run_client()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("client exited non-zero"))),
    ])
    return emit_report("E2-LS5-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
