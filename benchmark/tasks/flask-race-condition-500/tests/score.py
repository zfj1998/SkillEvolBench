#!/usr/bin/env python3
"""
Scoring rubric for E1-LS1-T1: flask-race-condition-500

Reads pytest JSON reports from test_outcome.py and test_process.py,
maps each test to its rubric dimension, and computes the weighted score.

Rubric:
  Public tests (P1-P5)             15%   proportional
  Hidden concurrency (H1-H4)      35%   proportional
  Hidden boundary+perf (H5-H8)    15%   proportional
  P1+P2: modification target      15%   utils.py modified; 0 if only routes.py
  P3+P4: thread-safety mechanism   15%   proper mechanism present
  P5: no exception swallowing       5%   not silencing KeyError

Usage:
    python score.py <outcome_report.json> <process_report.json>
    # or without args to run pytest inline (requires pytest installed)
"""

import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
# Rubric definition
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Dimension:
    name: str
    weight: float               # percentage points (total = 100)
    test_ids: List[str]         # pytest node IDs (substring match)
    scoring: str = "proportional"  # "proportional" | "all_or_nothing"


RUBRIC: List[Dimension] = [
    Dimension(
        name="Public tests (P1-P5)",
        weight=15.0,
        test_ids=["TestPublic::test_p1_", "TestPublic::test_p2_", "TestPublic::test_p3_",
                  "TestPublic::test_p4_", "TestPublic::test_p5_"],
        scoring="proportional",
    ),
    Dimension(
        name="Hidden concurrency (H1-H4)",
        weight=35.0,
        test_ids=["test_h1_", "test_h2_", "test_h3_", "test_h4_"],
        scoring="proportional",
    ),
    Dimension(
        name="Hidden boundary+perf (H5-H8)",
        weight=15.0,
        test_ids=["test_h5_", "test_h6_", "test_h7_", "test_h8_"],
        scoring="proportional",
    ),
    Dimension(
        name="P1+P2: modification target",
        weight=15.0,
        test_ids=["TestProcessP1P2"],
        scoring="all_or_nothing",
    ),
    Dimension(
        name="P3+P4: thread-safety mechanism",
        weight=15.0,
        test_ids=["TestProcessP3P4"],
        scoring="all_or_nothing",
    ),
    Dimension(
        name="P5: no exception swallowing",
        weight=5.0,
        test_ids=["TestProcessP5"],
        scoring="all_or_nothing",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Score computation
# ═══════════════════════════════════════════════════════════════════════════

def _match_tests(test_results: Dict[str, bool], patterns: List[str]) -> Dict[str, bool]:
    """Find all test results whose node ID contains any of the patterns."""
    matched = {}
    for node_id, passed in test_results.items():
        for pat in patterns:
            if pat in node_id.lower():
                matched[node_id] = passed
                break
    return matched


def compute_score(test_results: Dict[str, bool]) -> Dict[str, any]:
    """Compute weighted score from a flat dict of {test_node_id: passed}."""
    dimensions = []
    total_score = 0.0

    for dim in RUBRIC:
        matched = _match_tests(test_results, [p.lower() for p in dim.test_ids])
        n_total = len(matched)
        n_passed = sum(1 for v in matched.values() if v)

        if n_total == 0:
            # No matching tests found — dimension not evaluated
            dim_score = 0.0
            ratio = 0.0
        elif dim.scoring == "proportional":
            ratio = n_passed / n_total
            dim_score = dim.weight * ratio
        else:  # all_or_nothing
            ratio = 1.0 if n_passed == n_total else 0.0
            dim_score = dim.weight * ratio

        total_score += dim_score
        dimensions.append({
            "name": dim.name,
            "weight": dim.weight,
            "tests_matched": n_total,
            "tests_passed": n_passed,
            "scoring": dim.scoring,
            "ratio": round(ratio, 3),
            "score": round(dim_score, 2),
        })

    return {
        "total_score": round(total_score, 2),
        "max_score": 100.0,
        "dimensions": dimensions,
    }


def load_pytest_json(path: str) -> Dict[str, bool]:
    """Parse pytest --json-report output into {node_id: passed}."""
    with open(path) as f:
        data = json.load(f)
    results = {}
    for test in data.get("tests", []):
        node_id = test.get("nodeid", "")
        outcome = test.get("outcome", "")
        results[node_id] = (outcome == "passed")
    return results


def print_report(report: Dict[str, any]) -> None:
    print("=" * 65)
    print(f"  E1-LS1-T1 SCORING RUBRIC — Total: {report['total_score']}/{report['max_score']}")
    print("=" * 65)
    for dim in report["dimensions"]:
        status = "✓" if dim["ratio"] == 1.0 else ("△" if dim["ratio"] > 0 else "✗")
        print(
            f"  {status}  {dim['name']:<40s}  "
            f"{dim['tests_passed']}/{dim['tests_matched']}  "
            f"({dim['scoring'][:4]})  "
            f"{dim['score']:5.1f} / {dim['weight']:.0f}"
        )
    print("-" * 65)
    print(f"  TOTAL: {report['total_score']:.1f} / {report['max_score']:.0f}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Read from pytest JSON reports
        outcome_results = load_pytest_json(sys.argv[1])
        process_results = load_pytest_json(sys.argv[2])
        all_results = {**outcome_results, **process_results}
    else:
        print("Usage: python score.py <outcome_report.json> <process_report.json>")
        print()
        print("To generate pytest JSON reports:")
        print("  pip install pytest pytest-json-report")
        print("  pytest verifier/test_outcome.py --json-report --json-report-file=outcome.json")
        print("  pytest verifier/test_process.py --json-report --json-report-file=process.json")
        print("  python score.py outcome.json process.json")
        sys.exit(1)

    report = compute_score(all_results)
    print_report(report)

    # Also write machine-readable output
    with open("score_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Written to score_report.json")
