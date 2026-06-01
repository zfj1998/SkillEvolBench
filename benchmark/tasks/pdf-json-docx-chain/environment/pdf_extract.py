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
            # BUG: starter omits derived profit.
        }
    return data
