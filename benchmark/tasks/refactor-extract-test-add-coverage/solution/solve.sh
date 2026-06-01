#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path

Path("analyzer.py").write_text(r'''import math


def _clean_values(values):
    if values is None:
        raise ValueError("values cannot be None")
    cleaned = []
    for value in values:
        if not isinstance(value, (int, float)):
            raise TypeError("all values must be numeric")
        cleaned.append(float(value))
    return cleaned


def _basic_stats(cleaned):
    if not cleaned:
        return {"count": 0, "mean": 0.0, "median": 0.0, "stddev": 0.0, "q1": 0.0, "q3": 0.0, "spread": 0.0, "ordered": []}
    ordered = sorted(cleaned)
    count = len(ordered)
    mean = sum(ordered) / count
    median = (ordered[count // 2] if count % 2 else (ordered[count // 2 - 1] + ordered[count // 2]) / 2)
    variance = sum((value - mean) ** 2 for value in ordered) / count
    return {
        "count": count,
        "mean": mean,
        "median": median,
        "stddev": math.sqrt(variance),
        "q1": ordered[count // 4],
        "q3": ordered[(count * 3) // 4],
        "spread": ordered[-1] - ordered[0],
        "ordered": ordered,
    }


def _detect_outliers(ordered, q1, q3):
    if not ordered:
        return []
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [value for value in ordered if value < lower or value > upper]
def analyze_data(values):
    cleaned = _clean_values(values)
    stats = _basic_stats(cleaned)
    negatives = [value for value in cleaned if value < 0]
    zeros = [value for value in cleaned if value == 0]
    outliers = _detect_outliers(stats["ordered"], stats["q1"], stats["q3"])
    count = stats["count"]
    negative_ratio = len(negatives) / count if count else 0.0
    report = "stable"
    if count == 0:
        report = "empty_input"
    elif stats["spread"] > 100:
        report = "wide_spread"
    elif negative_ratio > 0.5:
        report = "mostly_negative"
    elif outliers and negative_ratio == 0:
        report = "positive_outliers"
    return {
        "count": count,
        "mean": stats["mean"],
        "median": stats["median"],
        "stddev": stats["stddev"],
        "q1": stats["q1"],
        "q3": stats["q3"],
        "outliers": outliers,
        "spread": stats["spread"],
        "negative_ratio": negative_ratio,
        "report": report,
        "zero_count": len(zeros),
        "error": "empty input" if count == 0 else None,
    }
''', encoding="utf-8")
Path("instruction.md").write_text("Refactor with coverage-driven tests for edge cases and preserve behavior.\n", encoding="utf-8")

tests = Path("public_tests/test_analyzer.py")
extra = '''

def test_empty_input_returns_controlled_error():
    result = analyze_data([])
    assert result["report"] == "empty_input"


def test_single_element_stats():
    result = analyze_data([42])
    assert result["mean"] == 42
    assert result["stddev"] == 0


def test_all_equal_values_have_zero_stddev():
    result = analyze_data([5, 5, 5])
    assert result["stddev"] == 0
    assert result["outliers"] == []


def test_negative_heavy_distribution():
    assert analyze_data([-10, -5, -2, 1])["report"] == "mostly_negative"


def test_wide_spread_distribution():
    assert analyze_data([1, 2, 3, 250])["report"] == "wide_spread"


def test_coverage_guard_for_edge_cases():
    # coverage: keep edge-case branches exercised after the refactor
    assert analyze_data([0])["zero_count"] == 1
'''
current = tests.read_text(encoding="utf-8")
if "test_empty_input_returns_controlled_error" not in current:
    tests.write_text(current.rstrip() + extra + "\n", encoding="utf-8")
PY
