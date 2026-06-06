from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "query_electronics_report.py"
DB_PATH = PROJECT_ROOT / "products.db"
OUTPUT = PROJECT_ROOT / "output.json"
INVALID_NULLS = {"", "na", "n/a", "null", "none"}
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")


def normalize_category(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    for char in ZERO_WIDTH:
        text = text.replace(char, "")
    return " ".join(text.strip().lower().split())


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


def expected_payload() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, name, category, price, stock_quantity, active FROM products ORDER BY id").fetchall()
    finally:
        conn.close()

    records = []
    price_sum = Decimal("0.00")
    stock_sum = 0
    for row in rows:
        if row["active"] != 1:
            continue
        if normalize_category(row["category"]) != "electronics":
            continue
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
                "category": "Electronics",
                "price": round_money(price),
                "stock_quantity": stock,
            }
        )
    return {
        "row_count": len(records),
        "average_price": round_money(float(price_sum / len(records))),
        "total_stock": stock_sum,
        "records": records,
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
            ("output_exists", lambda: run_script()[0].returncode == 0 and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output.json missing"))),
            ("returns_some_rows", lambda: run_script()[1].get("row_count", 0) > 0 or (_ for _ in ()).throw(AssertionError("no rows returned"))),
        ],
    )

    def check_expected_count() -> None:
        payload = run_script()[1]
        assert payload["row_count"] == expected["row_count"], f"expected {expected['row_count']} rows"
        assert 850 <= payload["row_count"] <= 1050, "row count not in expected Electronics band"

    def check_records() -> None:
        payload = run_script()[1]
        ids = [row["id"] for row in payload["records"]]
        assert len(ids) == len(set(ids)), "duplicate ids in output"
        assert [row["id"] for row in expected["records"]] == ids, "records differ from cleaned extract"
        assert all(row["category"] == "Electronics" for row in payload["records"]), "category not normalized"

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("row_count_matches_expected_band", check_expected_count),
            ("rows_are_complete_and_ordered", check_records),
            ("aggregate_metrics_match", lambda: run_script()[1]["average_price"] == expected["average_price"] and run_script()[1]["total_stock"] == expected["total_stock"] or (_ for _ in ()).throw(AssertionError("aggregate metrics mismatch"))),
            ("sanity_metadata_present", lambda: run_script()[1]["rowcount_audit"]["rowcount_reasonable"] and run_script()[1]["requery_performed"] is True or (_ for _ in ()).throw(AssertionError("sanity metadata missing"))),
        ],
    )
    return emit_report("E3-LS5-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
