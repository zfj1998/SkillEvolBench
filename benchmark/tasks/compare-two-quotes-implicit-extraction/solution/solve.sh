#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/charge_policy.py" <<'__SKILL_EVOL_REFERENCE_CHARGE_POLICY_PY_0__'
from __future__ import annotations


def total_cost(quote: dict) -> float:
    return round(float(quote["quoted_total"]) + float(quote.get("shipping", 0.0)), 2)
__SKILL_EVOL_REFERENCE_CHARGE_POLICY_PY_0__
cat > "$PROJECT_ROOT/quote_parser.py" <<'__SKILL_EVOL_REFERENCE_QUOTE_PARSER_PY_0__'
from __future__ import annotations

import re


def grab(text: str, pattern: str, default=None):
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else default


def parse_quote_text(text: str, supplier: str) -> dict:
    qty = int(grab(text, r"Qty:\s*(\d+)"))
    unit_price = float(grab(text, r"Unit Price:\s*\$(\d+(?:\.\d+)?)"))
    quoted_total = float(
        grab(text, r"Quoted Total(?: \(excluding shipping\))?:\s*\$(\d+(?:,\d{3})*(?:\.\d+)?)").replace(",", "")
    )
    shipping_match = grab(text, r"(?:Shipping|Freight)(?: fee)?(?: of)?\s*\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "0")
    shipping = float(shipping_match.replace(",", ""))
    return {
        "supplier": supplier,
        "item": grab(text, r"Item:\s*([^\n]+)"),
        "qty": qty,
        "unit_price": unit_price,
        "quoted_total": quoted_total,
        "shipping": shipping,
        "warranty": grab(text, r"Warranty:\s*([^\n]+)"),
        "delivery": grab(text, r"Delivery:\s*([^\n]+)"),
    }
__SKILL_EVOL_REFERENCE_QUOTE_PARSER_PY_0__
cat > "$PROJECT_ROOT/analyzer.py" <<'__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__'
import json
from pathlib import Path

from charge_policy import total_cost
from pypdf import PdfReader
from quote_parser import parse_quote_text

ROOT = Path(__file__).resolve().parent


def read_pdf(path):
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def compare(a, b):
    better = "A" if a["total_cost"] <= b["total_cost"] else "B"
    return {
        "recommended_supplier": better,
        "basis": "lower total cost after accounting for shipping/freight differences",
        "quote_a_total_cost": a["total_cost"],
        "quote_b_total_cost": b["total_cost"],
        "result_exists": True,
    }


def main():
    a = parse_quote_text(read_pdf(ROOT / "supplier_a_quote.pdf"), "A")
    b = parse_quote_text(read_pdf(ROOT / "supplier_b_quote.pdf"), "B")
    a["total_cost"] = total_cost(a)
    b["total_cost"] = total_cost(b)
    print(json.dumps({"quote_a": a, "quote_b": b, "comparison": compare(a, b)}, indent=2))


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__
