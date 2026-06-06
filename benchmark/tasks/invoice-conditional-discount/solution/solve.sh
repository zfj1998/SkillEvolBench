#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/analyzer.py" <<'__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__'
import json
import sys
from pathlib import Path
from typing import Dict, List

from invoice_reader import extract_text, iter_clean_lines, parse_line_item_rows
from pricing_policy import DISCOUNT_CONDITION, should_apply_discount, tax_base_after_discount


def parse_invoice(pdf_path: Path) -> Dict:
    text = extract_text(pdf_path)
    lines = list(iter_clean_lines(text))

    invoice_number = None
    line_items = parse_line_item_rows(lines)
    subtotal = discount_amount = state_tax_amount = federal_tax_amount = total = None

    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("Invoice Number:"):
            invoice_number = ln.split(":", 1)[1].strip()
            i += 1
            continue
        if ln == DISCOUNT_CONDITION:
            i += 1
            continue
        if ln == "Subtotal" and i + 1 < len(lines):
            subtotal = float(lines[i + 1]); i += 2; continue
        if ln == "Discount" and i + 1 < len(lines):
            discount_amount = float(lines[i + 1]); i += 2; continue
        if ln.startswith("State Tax") and i + 1 < len(lines):
            state_tax_amount = float(lines[i + 1]); i += 2; continue
        if ln.startswith("Federal Tax") and i + 1 < len(lines):
            federal_tax_amount = float(lines[i + 1]); i += 2; continue
        if ln == "Total" and i + 1 < len(lines):
            total = float(lines[i + 1]); i += 2; continue
        i += 1

    tax_base = tax_base_after_discount(subtotal, discount_amount)
    discount_applied = should_apply_discount(subtotal, discount_amount, strict=True)
    return {
        "invoice_number": invoice_number,
        "line_items": sorted(line_items, key=lambda row: row["index"]),
        "subtotal": subtotal,
        "discount": {
            "condition": DISCOUNT_CONDITION,
            "amount": discount_amount,
            "applied": discount_applied,
        },
        "tax": {
            "state": {"rate": 0.0825, "base": tax_base, "amount": state_tax_amount},
            "federal": {"rate": 0.025, "base": tax_base, "amount": federal_tax_amount},
        },
        "total": total,
    }


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python analyzer.py <pdf1> [<pdf2> ...]", file=sys.stderr)
        return 1
    payload = {"invoices": [parse_invoice(Path(path)) for path in argv[1:]]}
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__
