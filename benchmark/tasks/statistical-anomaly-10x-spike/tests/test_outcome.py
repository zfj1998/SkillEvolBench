from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "build_quarterly_revenue_report.py"
CSV_PATH = PROJECT_ROOT / "transactions.csv"
OUTPUT = PROJECT_ROOT / "output.json"


def load_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            dt = datetime.fromisoformat(row["date"])
            quarter = f"Q{((dt.month - 1) // 3) + 1}"
            rows.append(
                {
                    "transaction_id": row["transaction_id"],
                    "date": row["date"],
                    "amount": float(row["amount"]),
                    "batch_id": row["batch_id"],
                    "quarter": quarter,
                }
            )
    return rows


def quarter_totals(rows: list[dict[str, object]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[str(row["quarter"])] += float(row["amount"])
    return {quarter: round(total, 2) for quarter, total in sorted(totals.items())}


def expected_duplicate_groups(rows: list[dict[str, object]]) -> dict[str, list[str]]:
    by_batch: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        by_batch[str(row["batch_id"])].append((str(row["date"]), round(float(row["amount"]), 2)))
    by_fingerprint: dict[tuple, list[str]] = defaultdict(list)
    for batch_id, batch_rows in by_batch.items():
        by_fingerprint[tuple(sorted(batch_rows))].append(batch_id)
    return {batches[0]: sorted(batches) for batches in by_fingerprint.values() if len(batches) > 1}


def dedupe_rows(rows: list[dict[str, object]], duplicate_groups: dict[str, list[str]]) -> list[dict[str, object]]:
    redundant_batches = {batch_id for batches in duplicate_groups.values() for batch_id in batches[1:]}
    return [row for row in rows if str(row["batch_id"]) not in redundant_batches]


def run_script() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    rows = load_rows()
    expected_raw = quarter_totals(rows)
    duplicate_groups = expected_duplicate_groups(rows)
    expected_corrected = quarter_totals(dedupe_rows(rows, duplicate_groups))
    expected_baseline = round(float(median(expected_raw.values())), 2)

    public = run_checks(
        "public",
        [
            ("output_exists", lambda: run_script()[0].returncode == 0 and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output missing"))),
            ("returns_quarters", lambda: len(run_script()[1].get("quarterly_revenue", {})) == 4 or (_ for _ in ()).throw(AssertionError("quarter data missing"))),
        ],
    )

    def check_anomaly() -> None:
        payload = run_script()[1]
        anomalies = payload.get("anomalies", [])
        assert anomalies, "expected anomaly not reported"
        assert anomalies[0]["quarter"] == "Q3", "Q3 should be flagged"
        assert "ratio_to_baseline" in anomalies[0], "anomaly should include ratio_to_baseline"

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("raw_quarterly_revenue_matches_input", lambda: run_script()[1]["quarterly_revenue"] == expected_raw or (_ for _ in ()).throw(AssertionError("raw quarterly totals mismatch"))),
            ("detects_q3_anomaly", check_anomaly),
            ("identifies_duplicate_import_batches", lambda: run_script()[1]["duplicate_batches"] == duplicate_groups or (_ for _ in ()).throw(AssertionError("duplicate batches not fingerprinted correctly"))),
            ("corrected_quarters_match_deduped_view", lambda: run_script()[1]["corrected_quarterly_revenue"] == expected_corrected or (_ for _ in ()).throw(AssertionError("corrected totals mismatch"))),
            ("baseline_and_summary_are_grounded", lambda: run_script()[1]["sanity_summary"]["baseline_revenue"] == expected_baseline and run_script()[1]["sanity_summary"]["duplicate_batch_groups"] == len(duplicate_groups) or (_ for _ in ()).throw(AssertionError("summary metadata mismatch"))),
            ("root_cause_note_present", lambda: any("duplicate" in str(value).lower() or "import" in str(value).lower() for value in run_script()[1]["sanity_summary"].values()) or (_ for _ in ()).throw(AssertionError("root-cause note missing"))),
        ],
    )
    return emit_report("E3-LS5-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
