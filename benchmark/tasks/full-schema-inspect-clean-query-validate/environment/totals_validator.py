from __future__ import annotations


def build_validation_report(region_totals: dict[str, float], expected_totals: dict[str, float]) -> list[dict]:
    report = []
    for region, expected in sorted(expected_totals.items()):
        actual = round(float(region_totals.get(region, 0.0)), 2)
        delta = round(actual - expected, 2)
        delta_pct = abs(delta) / expected * 100 if expected else 0.0
        report.append(
            {
                "region": region,
                "actual_total": actual,
                "expected_total": expected,
                "delta": delta,
                "passed": delta_pct <= 10.0,
            }
        )
    return report
