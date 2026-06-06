#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "consistency_guard.py": dedent(
        """
        from __future__ import annotations


        def totals_consistent(overall_total: float, by_product_line_total: float) -> bool:
            if overall_total <= 0:
                return False
            return abs(by_product_line_total - overall_total) <= 0.01
        """
    ),
    "revenue_views.py": dedent(
        '''
        from __future__ import annotations

        import re
        import sqlite3
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

        from product_line_map import canonicalize_product_line

        TWOPLACES = Decimal("0.01")


        def _parse_amount(value: object) -> Decimal | None:
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


        def overall_revenue_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                """
                SELECT oi.product_line, oi.item_amount
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.status = 'POSTED'
                  AND o.is_test = 0
                ORDER BY oi.id
                """
            ).fetchall()


        def overall_total(conn: sqlite3.Connection) -> float:
            total = Decimal("0.00")
            for row in overall_revenue_rows(conn):
                canonical = canonicalize_product_line(row["product_line"])
                if canonical is None:
                    continue
                amount = _parse_amount(row["item_amount"])
                if amount is None:
                    continue
                total += amount
            return float(total.quantize(TWOPLACES, rounding=ROUND_HALF_UP))


        def normalized_product_line_totals(conn: sqlite3.Connection) -> dict[str, float]:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT oi.product_line, oi.item_amount, o.status, o.is_test
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.status = 'POSTED'
                  AND o.is_test = 0
                ORDER BY oi.id
                """
            ).fetchall()

            totals: dict[str, Decimal] = {}
            for row in rows:
                canonical = canonicalize_product_line(row["product_line"])
                if canonical is None:
                    continue
                amount = _parse_amount(row["item_amount"])
                if amount is None:
                    continue
                totals[canonical] = totals.get(canonical, Decimal("0.00")) + amount

            return {
                key: float(value.quantize(TWOPLACES, rounding=ROUND_HALF_UP))
                for key, value in sorted(totals.items())
            }
        '''
    ),
    "reconcile_revenue_views.py": dedent(
        """
        from __future__ import annotations

        import json
        import sqlite3
        from pathlib import Path

        from consistency_guard import totals_consistent
        from revenue_views import normalized_product_line_totals, overall_total

        DB_PATH = Path("revenue.db")
        OUTPUT_PATH = Path("output.json")


        def main() -> None:
            conn = sqlite3.connect(DB_PATH)
            try:
                overall = overall_total(conn)
                by_product_line = normalized_product_line_totals(conn)
            finally:
                conn.close()

            by_product_line_total = round(sum(by_product_line.values()), 2)
            difference = round(by_product_line_total - overall, 2)
            output = {
                "overall_total": overall,
                "product_line_total": by_product_line_total,
                "match": totals_consistent(overall, by_product_line_total),
                "difference": difference,
                "by_product_line": by_product_line,
                "mismatch_reason": None,
            }
            OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


        if __name__ == "__main__":
            main()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
