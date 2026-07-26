from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()
SCRIPT = PROJECT_ROOT / "count_active_customers.py"
DB_PATH = PROJECT_ROOT / "store.db"
OUTPUT = PROJECT_ROOT / "output.json"
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")


def normalize_email(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    for char in ZERO_WIDTH:
        text = text.replace(char, "")
    text = text.strip().lower()
    if text in {"", "null", "none", "na"}:
        return None
    return text


def expected_counts() -> dict[str, object]:
    from decimal import Decimal, InvalidOperation
    from datetime import datetime

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        customers = conn.execute("SELECT id, email FROM customers ORDER BY id").fetchall()
        orders = conn.execute("SELECT customer_id, amount, order_date, status FROM orders ORDER BY id").fetchall()
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
            logical_customers[canonical_id] = True
        else:
            if email not in by_email:
                by_email[email] = customer_id
                logical_customers[customer_id] = True
            canonical_id = by_email[email]
        canonical_by_customer_id[customer_id] = canonical_id

    def valid_amount(value: object) -> bool:
        if value is None:
            return False
        text = str(value).strip().replace("$", "")
        if not text:
            return False
        # Commas are valid only as conventional three-digit thousands
        # separators.  Strings such as "1,2,3" are malformed data, not 123.
        if "," in text:
            if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
                return False
        elif not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
            return False
        try:
            amount = Decimal(text.replace(",", ""))
        except InvalidOperation:
            return False
        return amount > 0

    def valid_date(value: object) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                datetime.strptime(text, fmt)
                return True
            except ValueError:
                pass
        return False

    active_ids = set()
    for row in orders:
        canonical_id = canonical_by_customer_id.get(row["customer_id"])
        if canonical_id is None:
            continue
        if str(row["status"]).strip().lower() not in {"paid", "shipped"}:
            continue
        if not valid_amount(row["amount"]):
            continue
        if not valid_date(row["order_date"]):
            continue
        active_ids.add(canonical_id)

    logical_total = len(logical_customers)
    return {
        "logical_customer_total": logical_total,
        "active_customer_count": len(active_ids),
        "inactive_customer_count": logical_total - len(active_ids),
        "active_customer_ids": sorted(active_ids),
    }


def run_script() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = expected_counts()

    public = run_checks(
        "public",
        [
            ("output_exists", lambda: run_script()[0].returncode == 0 and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError("output missing"))),
            ("counts_present", lambda: "active_customer_count" in run_script()[1] and "inactive_customer_count" in run_script()[1] or (_ for _ in ()).throw(AssertionError("counts missing"))),
        ],
    )

    hidden = run_checks(
        "hidden",
        [
            ("script_succeeds", lambda: run_script()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(run_script()[0].stderr[:400]))),
            ("logical_total_is_correct", lambda: run_script()[1]["logical_customer_total"] == expected["logical_customer_total"] == 1000 or (_ for _ in ()).throw(AssertionError("logical total mismatch"))),
            ("active_count_uses_valid_orders_only", lambda: run_script()[1]["active_customer_count"] == expected["active_customer_count"] == 700 or (_ for _ in ()).throw(AssertionError("active customer count mismatch"))),
            ("inactive_count_reconciles", lambda: run_script()[1]["inactive_customer_count"] == expected["inactive_customer_count"] and run_script()[1]["active_customer_count"] + run_script()[1]["inactive_customer_count"] == run_script()[1]["logical_customer_total"] or (_ for _ in ()).throw(AssertionError("inactive count mismatch"))),
            ("active_customer_ids_match_ground_truth", lambda: run_script()[1]["active_customer_ids"] == expected["active_customer_ids"] or (_ for _ in ()).throw(AssertionError("active id set mismatch"))),
        ],
    )
    return emit_report("E3-LS5-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
