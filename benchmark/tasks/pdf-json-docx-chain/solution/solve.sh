#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/pdf_extract.py" <<'__SKILL_EVOL_REFERENCE_PDF_EXTRACT_PY_0__'
from __future__ import annotations

import re
from pypdf import PdfReader


def extract_financials(pdf_path) -> dict:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    pattern = re.compile(r"(Q[1-4])\s+Revenue:\s+([\d,]+)\s+Expenses:\s+([\d,]+)")
    data = {}
    for quarter, revenue, expenses in pattern.findall(text):
        revenue_i = int(revenue.replace(",", ""))
        expenses_i = int(expenses.replace(",", ""))
        data[quarter] = {
            "revenue": revenue_i,
            "expenses": expenses_i,
            "profit": revenue_i - expenses_i,
        }
    return data
__SKILL_EVOL_REFERENCE_PDF_EXTRACT_PY_0__
cat > "$PROJECT_ROOT/docx_writer.py" <<'__SKILL_EVOL_REFERENCE_DOCX_WRITER_PY_0__'
from __future__ import annotations

from docx import Document


def build_docx(path, data: dict) -> None:
    doc = Document()
    doc.add_heading("Quarterly Financial Report", level=1)
    table = doc.add_table(rows=1, cols=4)
    header = table.rows[0].cells
    header[0].text = "Quarter"
    header[1].text = "Revenue"
    header[2].text = "Expenses"
    header[3].text = "Profit"
    for quarter, values in data.items():
        row = table.add_row().cells
        row[0].text = quarter
        row[1].text = str(values["revenue"])
        row[2].text = str(values["expenses"])
        row[3].text = str(values["profit"])
    doc.save(str(path))
__SKILL_EVOL_REFERENCE_DOCX_WRITER_PY_0__
cat > "$PROJECT_ROOT/pipeline.py" <<'__SKILL_EVOL_REFERENCE_PIPELINE_PY_0__'
import json
from pathlib import Path

from docx_writer import build_docx
from json_bridge import write_json
from pdf_extract import extract_financials

ROOT = Path(__file__).resolve().parent
PDF = ROOT / "quarterly_report.pdf"
JSON_OUT = ROOT / "extracted.json"
DOCX_OUT = ROOT / "report.docx"


def main():
    financial_data = extract_financials(PDF)
    for values in financial_data.values():
        values["profit"] = values["profit"]
    write_json(JSON_OUT, financial_data)
    # build_docx renders a structured add_table output with the derived profit column.
    build_docx(DOCX_OUT, financial_data)


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_PIPELINE_PY_0__
