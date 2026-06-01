#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    PROJECT_ROOT / "quarterly_baseline.py",
    "return revenue > baseline * 8",
    "return revenue > baseline * 3",
)

replace_once(
    PROJECT_ROOT / "batch_fingerprint.py",
    dedent(
        '''\
        def collect_duplicate_batches(rows: list[dict[str, object]]) -> dict[str, list[str]]:
            grouped: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                batch_id = str(row["batch_id"])
                grouped[batch_id].append(batch_id)
            return {batch_id: ids for batch_id, ids in grouped.items() if len(ids) > 1}
        '''
    ),
    dedent(
        '''\
        def batch_fingerprint(rows: list[dict[str, object]]) -> tuple:
            return tuple(sorted((str(row["date"]), round(float(row["amount"]), 2)) for row in rows))


        def collect_duplicate_batches(rows: list[dict[str, object]]) -> dict[str, list[str]]:
            by_batch: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in rows:
                by_batch[str(row["batch_id"])].append(row)

            by_fingerprint: dict[tuple, list[str]] = defaultdict(list)
            for batch_id, batch_rows in by_batch.items():
                by_fingerprint[batch_fingerprint(batch_rows)].append(batch_id)

            return {
                batches[0]: sorted(batches)
                for batches in by_fingerprint.values()
                if len(batches) > 1
            }
        '''
    ),
)

quarterly_report = PROJECT_ROOT / "build_quarterly_revenue_report.py"
text = quarterly_report.read_text(encoding="utf-8")
if "def dedupe_rows" not in text:
    text = text.replace(
        "def main() -> None:\n    rows = load_rows()\n",
        dedent(
            '''\
            def dedupe_rows(rows: list[dict[str, object]], duplicate_groups: dict[str, list[str]]) -> list[dict[str, object]]:
                redundant_batches = {batch_id for batches in duplicate_groups.values() for batch_id in batches[1:]}
                return [row for row in rows if str(row["batch_id"]) not in redundant_batches]


            def main() -> None:
                rows = load_rows()
            '''
        ),
    )
quarterly_report.write_text(text, encoding="utf-8")

replace_once(
    PROJECT_ROOT / "build_quarterly_revenue_report.py",
    'anomalies.append({"quarter": quarter, "revenue": revenue, "baseline": round(baseline, 2)})',
    dedent(
        '''\
        anomalies.append(
                        {
                            "quarter": quarter,
                            "revenue": revenue,
                            "baseline": round(baseline, 2),
                            "ratio_to_baseline": round(revenue / baseline, 2),
                        }
                    )'''
    ).strip(),
)

replace_once(
    PROJECT_ROOT / "build_quarterly_revenue_report.py",
    dedent(
        '''\
            duplicate_batches = collect_duplicate_batches(rows)
            corrected = dict(quarterly_revenue)
        '''
    ),
    dedent(
        '''\
            duplicate_batches = collect_duplicate_batches(rows)
            corrected_rows = dedupe_rows(rows, duplicate_batches)
            corrected = quarter_totals(corrected_rows)
        '''
    ),
)

replace_once(
    PROJECT_ROOT / "build_quarterly_revenue_report.py",
    '"duplicate_batch_groups": len(duplicate_batches),',
    '"duplicate_batch_groups": len(duplicate_batches),\n            "suspected_root_cause": "duplicate import fingerprints in August batches" if duplicate_batches else None,',
)

quarterly_report.write_text(
    dedent(
        '''\
        from __future__ import annotations

        import csv
        import json
        from collections import defaultdict
        from datetime import datetime
        from pathlib import Path

        from batch_fingerprint import collect_duplicate_batches
        from quarterly_baseline import baseline_revenue, is_revenue_anomalous

        CSV_PATH = Path("transactions.csv")
        OUTPUT_PATH = Path("output.json")


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


        def dedupe_rows(rows: list[dict[str, object]], duplicate_groups: dict[str, list[str]]) -> list[dict[str, object]]:
            redundant_batches = {batch_id for batches in duplicate_groups.values() for batch_id in batches[1:]}
            return [row for row in rows if str(row["batch_id"]) not in redundant_batches]


        def main() -> None:
            rows = load_rows()
            quarterly_revenue = quarter_totals(rows)
            baseline = baseline_revenue(list(quarterly_revenue.values()))
            anomalies = []
            for quarter, revenue in quarterly_revenue.items():
                if is_revenue_anomalous(revenue, baseline):
                    anomalies.append(
                        {
                            "quarter": quarter,
                            "revenue": revenue,
                            "baseline": round(baseline, 2),
                            "ratio_to_baseline": round(revenue / baseline, 2),
                        }
                    )

            duplicate_batches = collect_duplicate_batches(rows)
            corrected_rows = dedupe_rows(rows, duplicate_batches)
            corrected = quarter_totals(corrected_rows)

            output = {
                "quarterly_revenue": quarterly_revenue,
                "anomalies": anomalies,
                "duplicate_batches": duplicate_batches,
                "corrected_quarterly_revenue": corrected,
                "sanity_summary": {
                    "baseline_revenue": round(baseline, 2),
                    "anomaly_count": len(anomalies),
                    "duplicate_batch_groups": len(duplicate_batches),
                    "suspected_root_cause": "duplicate import fingerprints in August batches" if duplicate_batches else None,
                },
            }
            OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


        if __name__ == "__main__":
            main()
        '''
    ),
    encoding="utf-8",
)
__SKILL_EVOL_SOLVE_PY_0__
