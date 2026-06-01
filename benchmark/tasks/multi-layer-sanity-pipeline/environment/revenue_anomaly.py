from __future__ import annotations

from collections import defaultdict
from statistics import median


def detect_revenue_anomalies(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], float]:
    by_region = defaultdict(list)
    total_revenue = 0.0
    for row in rows:
        revenue = float(row["revenue"])
        by_region[str(row["region"])].append((str(row["month"]), revenue, str(row["batch_id"])))
        total_revenue += revenue

    anomalies = []
    for region, values in by_region.items():
        baseline = median(revenue for _, revenue, _ in values)
        for month, revenue, batch_id in values:
            if baseline > 0 and revenue > baseline * 3:
                anomalies.append(
                    {
                        "kind": "revenue_spike",
                        "source": "monthly_revenue",
                        "detail": f"{month} {region} revenue {revenue:.2f} exceeds baseline {baseline:.2f}",
                        "impact": "medium",
                        "month": month,
                        "region": region,
                        "batch_id": batch_id,
                    }
                )
    return anomalies, round(total_revenue, 2)
