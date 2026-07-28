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
    "order_validity.py": dedent(
        """
        from __future__ import annotations

        import re
        from datetime import datetime
        from decimal import Decimal, InvalidOperation


        def valid_order_status(value: object) -> bool:
            return str(value).strip().lower() in {"paid", "shipped"}


        def parse_amount(value: object) -> Decimal | None:
            if value is None:
                return None
            text = str(value).strip().replace("$", "")
            if not text:
                return None
            if "," in text:
                if not re.fullmatch(r"[+-]?\\d{1,3}(?:,\\d{3})+(?:\\.\\d+)?", text):
                    return None
            elif not re.fullmatch(r"[+-]?\\d+(?:\\.\\d+)?", text):
                return None
            try:
                amount = Decimal(text.replace(",", ""))
            except InvalidOperation:
                return None
            return amount if amount > 0 else None


        def valid_order_date(value: object) -> bool:
            if value is None:
                return False
            text = str(value).strip()
            if not text:
                return False
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    datetime.strptime(text, fmt)
                    return True
                except ValueError:
                    pass
            return False
        """
    ),
    "activity_guard.py": dedent(
        """
        from __future__ import annotations

        from order_validity import parse_amount, valid_order_date, valid_order_status


        def has_order_activity(row: dict[str, object]) -> bool:
            if row.get("order_id") is None:
                return False
            if not valid_order_status(row.get("status")):
                return False
            if parse_amount(row.get("amount")) is None:
                return False
            if not valid_order_date(row.get("order_date")):
                return False
            return True
        """
    ),
    "count_active_customers.py": dedent(
        '''
        from __future__ import annotations

        import json
        import sqlite3
        from pathlib import Path

        from activity_guard import has_order_activity
        from customer_identity import normalize_email

        DB_PATH = Path("store.db")
        OUTPUT_PATH = Path("output.json")


        def main() -> None:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                customers = conn.execute("SELECT id, name, email FROM customers ORDER BY id").fetchall()
                joined_rows = conn.execute(
                    """
                    SELECT c.id AS customer_id, c.name, c.email, o.id AS order_id, o.status, o.amount, o.order_date
                    FROM customers c
                    LEFT JOIN orders o ON c.id = o.customer_id
                    ORDER BY c.id, o.id
                    """
                ).fetchall()
            finally:
                conn.close()

            canonical_by_customer_id = {}
            logical_customers = {}
            by_email = {}

            for row in customers:
                email = normalize_email(row["email"])
                customer_id = row["id"]
                if email is None:
                    canonical_id = customer_id
                    logical_customers[canonical_id] = {"id": canonical_id, "name": row["name"]}
                else:
                    if email not in by_email:
                        by_email[email] = customer_id
                        logical_customers[customer_id] = {"id": customer_id, "name": row["name"]}
                    canonical_id = by_email[email]
                canonical_by_customer_id[customer_id] = canonical_id

            active_ids = set()
            for row in joined_rows:
                canonical_id = canonical_by_customer_id.get(row["customer_id"])
                if canonical_id is None:
                    continue
                if has_order_activity(dict(row)):
                    active_ids.add(canonical_id)

            active_customer_ids = sorted(active_ids)
            logical_total = len(logical_customers)
            output = {
                "logical_customer_total": logical_total,
                "active_customer_count": len(active_customer_ids),
                "inactive_customer_count": logical_total - len(active_customer_ids),
                "active_customer_ids": active_customer_ids,
                "sanity": {
                    "active_le_total": len(active_customer_ids) <= logical_total,
                    "active_plus_inactive_equals_total": len(active_customer_ids) + (logical_total - len(active_customer_ids)) == logical_total,
                },
            }
            OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


        if __name__ == "__main__":
            main()
        '''
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
