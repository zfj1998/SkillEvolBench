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


def main() -> None:
    rows = load_rows()
    quarterly_revenue = quarter_totals(rows)
    baseline = baseline_revenue(list(quarterly_revenue.values()))
    anomalies = []
    for quarter, revenue in quarterly_revenue.items():
        if is_revenue_anomalous(revenue, baseline):
            anomalies.append({"quarter": quarter, "revenue": revenue, "baseline": round(baseline, 2)})

    duplicate_batches = collect_duplicate_batches(rows)
    corrected = dict(quarterly_revenue)

    output = {
        "quarterly_revenue": quarterly_revenue,
        "anomalies": anomalies,
        "duplicate_batches": duplicate_batches,
        "corrected_quarterly_revenue": corrected,
        "sanity_summary": {
            "baseline_revenue": round(baseline, 2),
            "anomaly_count": len(anomalies),
            "duplicate_batch_groups": len(duplicate_batches),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
