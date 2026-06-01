from __future__ import annotations

import re


def extract_section(report: str, page: str) -> str:
    pattern = rf"(?ms)^## .*?\(p\.\s*{page}\)\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, report)
    return match.group(0).strip() if match else ""
