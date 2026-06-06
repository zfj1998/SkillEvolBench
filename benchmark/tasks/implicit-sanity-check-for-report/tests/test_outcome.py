from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "build_march_sales_report.py"
DB_PATH = PROJECT_ROOT / "daily_sales.db"
OUTPUT = PROJECT_ROOT / "output.json"
INVALID_NULLS = {"", "na", "n/a", "null", "none"}


def normalize_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("/", "-")
    if not text:
        return None
    try:
        dt = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    if dt.year == 2024 and dt.month == 3:
        return dt.isoformat()
    return None


def parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in INVALID_NULLS:
        return None
    if text.startswith("$"):
        text = text[1:].strip()
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def parse_quantity(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def expected_report() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT id, date, product, amount, quantity FROM sales ORDER BY id").fetchall()]
    finally:
        conn.close()

    deduped = {}
    for row in rows:
        normalized_date = normalize_date(row["date"])
        amount = parse_amount(row["amount"])
        quantity = parse_quantity(row["quantity"])
        if normalized_date is None or amount is None or quantity is None:
            continue
        key = (normalized_date, str(row["product"]).strip(), str(amount), quantity)
        if key not in deduped or int(row["id"]) < int(deduped[key]["id"]):
            deduped[key] = {
                "id": row["id"],
                "date": normalized_date,
                "amount": amount,
            }

    by_day: dict[str, dict[str, object]] = defaultdict(lambda: {"revenue": Decimal("0.00"), "transactions": 0})
    for row in deduped.values():
        by_day[row["date"]]["revenue"] += row["amount"]
        by_day[row["date"]]["transactions"] += 1

    current = date(2024, 3, 1)
    end = date(2024, 3, 31)
    days = []
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    missing = [day for day in days if day not in by_day]
    total = sum((bucket["revenue"] for bucket in by_day.values()), Decimal("0.00"))
    return {
        "total_revenue": float(total.quantize(Decimal("0.01"))),
        "average_daily_revenue": float((total / len(by_day)).quantize(Decimal("0.01"))),
        "days_with_data": len(by_day),
        "missing_days": missing,
    }


def run_script() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = expected_report()

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("detects_missing_days", lambda: run_script()[1]["missing_days"] == expected["missing_days"] == ["2024-03-15", "2024-03-16"] or (_ for _ in ()).throw(AssertionError("missing day detection incorrect"))),
            ("marks_report_incomplete", lambda: run_script()[1]["completeness"] == "incomplete" and "2 days" in run_script()[1]["quality_note"] and "2024-03-15" in run_script()[1]["quality_note"] and "2024-03-16" in run_script()[1]["quality_note"] or (_ for _ in ()).throw(AssertionError("report not marked incomplete with missing dates"))),
            ("totals_use_valid_rows_only", lambda: run_script()[1]["total_revenue"] == expected["total_revenue"] and run_script()[1]["average_daily_revenue"] == expected["average_daily_revenue"] and run_script()[1]["days_with_data"] == expected["days_with_data"] or (_ for _ in ()).throw(AssertionError("totals or day count mismatch"))),
            ("daily_breakdown_matches_valid_days", lambda: len(run_script()[1]["daily_breakdown"]) == expected["days_with_data"] or (_ for _ in ()).throw(AssertionError("daily breakdown length mismatch"))),
        ],
    )
    return emit_report("E3-LS5-T4", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
