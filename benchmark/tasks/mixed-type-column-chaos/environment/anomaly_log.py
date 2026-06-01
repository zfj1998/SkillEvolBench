from __future__ import annotations


def build_anomaly_report(null_rows: int, parse_failures: int) -> dict:
    return {
        "null_like_rows": null_rows,
        "parse_failures": parse_failures,
    }
