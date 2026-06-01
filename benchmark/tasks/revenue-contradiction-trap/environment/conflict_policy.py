from __future__ import annotations


def summarize_revenue_conflict(evidence: list[dict]) -> dict:
    values = [item["value"] for item in evidence]
    # BUG: the legacy policy still smooths the discrepancy into one corrected figure.
    corrected = sum(values) / len(values)
    return {
        "annual_revenue": corrected,
        "source": "annual_report.pdf",
        "note": "corrected revenue extracted from report",
    }
