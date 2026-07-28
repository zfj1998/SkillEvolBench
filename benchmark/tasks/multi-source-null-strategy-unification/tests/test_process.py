from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
POLICY = PROJECT / "null_policy.py"
MERGE = PROJECT / "merge_inventory.py"
SCRIPT = PROJECT / "merge_supplier_inventory.py"
OUTPUT = PROJECT / "output.json"


def _run_merge():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def run():
    public = run_checks("public", [
        ("uses_keep_default_na_false", lambda: set(_run_merge()["source_null_summary"]) == {"supplier_a", "supplier_b", "supplier_c"} or (_ for _ in ()).throw(AssertionError("raw supplier null semantics were not preserved per source"))),
    ])
    hidden = run_checks("hidden", [
        (
            "source_aware_null_policy",
            lambda: _run_merge()["source_null_summary"]["supplier_c"]["missing_price"] > 0
            and _run_merge()["source_null_summary"]["supplier_c"]["out_of_stock_count"] > 0
            or (_ for _ in ()).throw(
                AssertionError("supplier C price sentinels and valid zero stock are not distinguished")
            ),
        ),
        (
            "merge_uses_null_policy",
            lambda: _run_merge()["record_count"] > 0
            and _run_merge()["missing_price_count"] > 0
            or (_ for _ in ()).throw(
                AssertionError("merge pipeline did not apply null standardization")
            ),
        ),
    ])
    return emit_report("E3-LS4-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
