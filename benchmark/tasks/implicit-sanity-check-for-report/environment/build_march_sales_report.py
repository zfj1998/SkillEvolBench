from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from calendar_guard import missing_days
from report_annotations import build_quality_note
from sales_cleaning import normalize_date, parse_amount, parse_quantity

DB_PATH = Path("daily_sales.db")
OUTPUT_PATH = Path("output.json")


def round_money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def main() -> None:
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
                "product": str(row["product"]).strip(),
                "amount": amount,
                "quantity": quantity,
            }

    by_day: dict[str, dict[str, object]] = defaultdict(lambda: {"revenue": Decimal("0.00"), "transactions": 0})
    for row in deduped.values():
        by_day[row["date"]]["revenue"] += row["amount"]
        by_day[row["date"]]["transactions"] += 1

    missing = missing_days(rows)
    completeness, quality_note = build_quality_note(missing)
    total_revenue = sum((bucket["revenue"] for bucket in by_day.values()), Decimal("0.00"))
    day_count = len(by_day)

    output = {
        "month": "2024-03",
        "total_revenue": round_money(total_revenue),
        "average_daily_revenue": round_money(total_revenue / day_count) if day_count else 0.0,
        "days_with_data": day_count,
        "missing_days": missing,
        "completeness": completeness,
        "quality_note": quality_note,
        "daily_breakdown": [
            {
                "date": day,
                "revenue": round_money(by_day[day]["revenue"]),
                "transactions": by_day[day]["transactions"],
            }
            for day in sorted(by_day)
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
