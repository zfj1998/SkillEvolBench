from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "reconcile_revenue_views.py"
DB_PATH = PROJECT_ROOT / "revenue.db"
OUTPUT = PROJECT_ROOT / "output.json"
TWOPLACES = Decimal("0.01")
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")
CANONICAL_MAP = {
    "software": "Software",
    "sw": "Software",
    "soft ware": "Software",
    "hardware": "Hardware",
    "hw": "Hardware",
    "hard ware": "Hardware",
    "services": "Services",
    "service": "Services",
    "svc": "Services",
    "consulting": "Consulting",
    "consult": "Consulting",
    "advisory": "Consulting",
}


def parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "null", "none", "bad"}:
        return None
    text = text.replace(",", "")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return amount if amount >= 0 else None


def canonicalize_product_line(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    for char in ZERO_WIDTH:
        text = text.replace(char, "")
    text = " ".join(text.strip().lower().split())
    return CANONICAL_MAP.get(text)


def expected_payload() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        items = conn.execute(
            """
            SELECT oi.product_line, oi.item_amount
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status = 'POSTED'
              AND o.is_test = 0
            ORDER BY oi.id
            """
        ).fetchall()
    finally:
        conn.close()

    overall = Decimal("0.00")
    by_line: dict[str, Decimal] = {}
    for row in items:
        canonical = canonicalize_product_line(row["product_line"])
        if canonical is None:
            continue
        amount = parse_amount(row["item_amount"])
        if amount is None:
            continue
        overall += amount
        by_line[canonical] = by_line.get(canonical, Decimal("0.00")) + amount

    by_line_clean = {
        key: float(value.quantize(TWOPLACES, rounding=ROUND_HALF_UP))
        for key, value in sorted(by_line.items())
    }
    overall_clean = float(overall.quantize(TWOPLACES, rounding=ROUND_HALF_UP))
    by_line_total = round(sum(by_line_clean.values()), 2)
    return {
        "overall_total": overall_clean,
        "product_line_total": by_line_total,
        "by_product_line": by_line_clean,
    }


def run_script() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = expected_payload()

    public = run_checks(
        "public",
        [
            ("output_exists", lambda: run_script()[0].returncode == 0 and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output missing"))),
            ("totals_present", lambda: "overall_total" in run_script()[1] and "product_line_total" in run_script()[1] or (_ for _ in ()).throw(AssertionError("totals missing"))),
        ],
    )

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("overall_total_is_correct", lambda: run_script()[1]["overall_total"] == expected["overall_total"] or (_ for _ in ()).throw(AssertionError("overall total mismatch"))),
            ("product_line_breakdown_is_correct", lambda: run_script()[1]["by_product_line"] == expected["by_product_line"] or (_ for _ in ()).throw(AssertionError("product-line breakdown mismatch"))),
            ("cross_query_totals_reconcile", lambda: run_script()[1]["product_line_total"] == expected["product_line_total"] and run_script()[1]["match"] is True and run_script()[1]["difference"] == 0.0 or (_ for _ in ()).throw(AssertionError("cross-query totals do not reconcile"))),
            ("mismatch_reason_cleared_after_fix", lambda: run_script()[1]["mismatch_reason"] in (None, "") or (_ for _ in ()).throw(AssertionError("mismatch reason should be cleared after fix"))),
        ],
    )
    return emit_report("E3-LS5-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
