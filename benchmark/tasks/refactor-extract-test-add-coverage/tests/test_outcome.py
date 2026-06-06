from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from analyzer import analyze_data
from verifier_lib.runtime import emit_report, print_report, run_checks


EXPECTED_KEYS = {
    "count", "mean", "median", "stddev", "q1", "q3", "outliers",
    "spread", "negative_ratio", "report", "zero_count", "error",
}


def _schema_complete_for_normal_input():
    result = analyze_data([1, 2, 3, 4, 5])
    missing = EXPECTED_KEYS - set(result)
    assert not missing, f"missing schema keys: {sorted(missing)}"
    for key in ["count", "mean", "median", "stddev", "q1", "q3", "spread", "negative_ratio", "zero_count"]:
        assert isinstance(result[key], (int, float)), f"{key} should be numeric"
    assert isinstance(result["outliers"], list)
    assert isinstance(result["report"], str)
    assert result["error"] is None or isinstance(result["error"], str)
    return result


def _empty_input_schema():
    result = analyze_data([])
    assert result["count"] == 0
    assert result["report"] == "empty_input"
    assert isinstance(result.get("error"), str) and result["error"]
    return result


def _single_element_no_outliers():
    result = analyze_data([42])
    assert result["mean"] == 42
    assert result["stddev"] == 0
    assert result["outliers"] == []
    return result


def _all_equal_no_outliers():
    result = analyze_data([5, 5, 5])
    assert result["stddev"] == 0
    assert result["outliers"] == []
    return result


def run():
    public = run_checks(
        "public",
        [
            ("basic_mean", lambda: analyze_data([1, 2, 3, 4, 5])["mean"] == 3.0 or (_ for _ in ()).throw(AssertionError("mean mismatch"))),
            ("basic_median", lambda: analyze_data([1, 2, 3, 4])["median"] == 2.5 or (_ for _ in ()).throw(AssertionError("median mismatch"))),
            ("schema_complete_for_normal_input", _schema_complete_for_normal_input),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("empty_input_schema", _empty_input_schema),
            ("all_equal_values", _all_equal_no_outliers),
            ("single_element_no_outliers", _single_element_no_outliers),
        ],
    )
    return emit_report("E1-LS3-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
