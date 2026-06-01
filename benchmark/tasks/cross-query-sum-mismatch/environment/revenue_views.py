from __future__ import annotations

import sqlite3

from product_line_map import canonicalize_product_line


def overall_revenue_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT id, total_amount
        FROM orders
        WHERE status = 'POSTED'
          AND is_test = 0
        """
    ).fetchall()


def product_line_revenue_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT oi.product_line, SUM(CAST(o.total_amount AS REAL)) AS revenue
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.status = 'POSTED'
          AND o.is_test = 0
        GROUP BY oi.product_line
        ORDER BY oi.product_line
        """
    ).fetchall()


def normalized_product_line_totals(conn: sqlite3.Connection) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in product_line_revenue_rows(conn):
        canonical = canonicalize_product_line(row["product_line"])
        if canonical is None:
            continue
        totals[canonical] = round(totals.get(canonical, 0.0) + float(row["revenue"]), 2)
    return dict(sorted(totals.items()))
