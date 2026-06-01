from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def iter_clean_lines(text: str) -> Iterable[str]:
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            yield line


def parse_line_item_rows(lines: list[str]) -> list[dict]:
    rows: list[dict] = []
    i = 0
    while i < len(lines):
        token = lines[i]
        if token.isdigit() and (i + 4) < len(lines):
            description, qty, currency, amount = lines[i + 1 : i + 5]
            if qty.isdigit() and currency in {"USD", "EUR", "JPY"}:
                try:
                    rows.append(
                        {
                            "index": int(token),
                            "description": description,
                            "qty": int(qty),
                            "currency": currency,
                            "amount": float(amount),
                        }
                    )
                    i += 5
                    continue
                except ValueError:
                    pass
        i += 1
    return rows
