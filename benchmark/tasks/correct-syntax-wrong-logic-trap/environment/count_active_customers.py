from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
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
