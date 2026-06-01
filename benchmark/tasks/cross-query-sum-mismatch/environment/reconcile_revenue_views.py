from __future__ import annotations

import json
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

from consistency_guard import totals_consistent
from revenue_views import normalized_product_line_totals, overall_revenue_rows

DB_PATH = Path("revenue.db")
OUTPUT_PATH = Path("output.json")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        overall_total_decimal = Decimal("0.00")
        for row in overall_revenue_rows(conn):
            try:
                overall_total_decimal += Decimal(str(row["total_amount"]).strip())
            except (InvalidOperation, ValueError):
                continue
        overall_total = round(float(overall_total_decimal), 2)
        by_product_line = normalized_product_line_totals(conn)
    finally:
        conn.close()

    by_product_line_total = round(sum(by_product_line.values()), 2)
    output = {
        "overall_total": overall_total,
        "product_line_total": by_product_line_total,
        "match": totals_consistent(overall_total, by_product_line_total),
        "difference": round(by_product_line_total - overall_total, 2),
        "by_product_line": by_product_line,
        "mismatch_reason": None,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
