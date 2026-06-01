from __future__ import annotations

import json
import math
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from category_normalizer import normalize_category
from rowcount_guard import evaluate_rowcount

DB_PATH = Path("products.db")
OUTPUT_PATH = Path("output.json")

INVALID_NULLS = {"", "na", "n/a", "null", "none"}


def parse_price(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in INVALID_NULLS:
        return None
    if text.startswith("$"):
        text = text[1:].strip()
    text = text.replace(",", "")
    try:
        price = float(text)
    except ValueError:
        return None
    if not math.isfinite(price) or price < 0:
        return None
    return price


def parse_stock(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in INVALID_NULLS:
        return None
    try:
        stock = float(text)
    except ValueError:
        return None
    if not math.isfinite(stock) or stock < 0 or not stock.is_integer():
        return None
    return int(stock)


def round_money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, name, category, price, stock_quantity, active
            FROM products
            WHERE active = 1
              AND lower(trim(category)) = ?
            ORDER BY id
            """,
            ("electronics",),
        ).fetchall()
    finally:
        conn.close()

    records: list[dict[str, object]] = []
    price_sum = Decimal("0.00")
    stock_sum = 0

    for row in rows:
        price = parse_price(row["price"])
        stock = parse_stock(row["stock_quantity"])
        if price is None or stock is None:
            continue
        price_sum += Decimal(str(price))
        stock_sum += stock
        records.append(
            {
                "id": row["id"],
                "name": row["name"],
                "category": normalize_category(row["category"]),
                "price": round_money(price),
                "stock_quantity": stock,
            }
        )

    rowcount_audit = evaluate_rowcount(len(records))
    average_price = round_money(float(price_sum / len(records))) if records else 0.0

    output = {
        "category": "Electronics",
        "row_count": len(records),
        "average_price": average_price,
        "total_stock": stock_sum,
        "rowcount_audit": rowcount_audit,
        "requery_performed": False,
        "records": records,
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
