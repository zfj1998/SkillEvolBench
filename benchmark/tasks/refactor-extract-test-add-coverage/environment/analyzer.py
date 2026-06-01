from __future__ import annotations

import math


def analyze_data(values):
    if values is None:
        raise ValueError("values cannot be None")

    cleaned = []
    for value in values:
        if not isinstance(value, (int, float)):
            raise TypeError("all values must be numeric")
        cleaned.append(float(value))

    negatives = []
    positives = []
    zeros = []
    value_buckets = {"negative": 0, "zero": 0, "positive": 0}
    for value in cleaned:
        if value < 0:
            negatives.append(value)
            value_buckets["negative"] += 1
        elif value == 0:
            zeros.append(value)
            value_buckets["zero"] += 1
        else:
            positives.append(value)
            value_buckets["positive"] += 1

    total = 0.0
    count = 0
    for value in cleaned:
        total += value
        count += 1
    mean = total / count

    ordered = sorted(cleaned)
    if len(ordered) % 2 == 0:
        mid = len(ordered) // 2
        median = (ordered[mid - 1] + ordered[mid]) / 2
    else:
        median = ordered[len(ordered) // 2]

    variance_total = 0.0
    for value in ordered:
        variance_total += (value - mean) ** 2
    stddev = math.sqrt(variance_total / len(ordered))

    q1_index = len(ordered) // 4
    q3_index = (len(ordered) * 3) // 4
    q1 = ordered[q1_index]
    q3 = ordered[q3_index]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    percentile_window = {"lower": lower, "upper": upper, "iqr": iqr}
    outliers = []
    for value in ordered:
        if value < lower or value > upper:
            outliers.append(value)

    spread = max(ordered) - min(ordered)
    negative_ratio = len(negatives) / len(ordered)
    zero_ratio = len(zeros) / len(ordered)
    has_zero_crossing = bool(negatives and positives)
    report = "stable"
    if spread > 100:
        report = "wide_spread"
    if negative_ratio > 0.5:
        report = "mostly_negative"
    if outliers and negative_ratio == 0:
        report = "positive_outliers"
    if has_zero_crossing and spread < 25:
        report = "crosses_zero"

    return {
        "count": len(ordered),
        "mean": mean,
        "median": median,
        "stddev": stddev,
        "q1": q1,
        "q3": q3,
        "outliers": outliers,
        "spread": spread,
        "negative_ratio": negative_ratio,
        "zero_ratio": zero_ratio,
        "report": report,
        "zero_count": len(zeros),
        "value_buckets": value_buckets,
        "percentile_window": percentile_window,
        "has_zero_crossing": has_zero_crossing,
    }
