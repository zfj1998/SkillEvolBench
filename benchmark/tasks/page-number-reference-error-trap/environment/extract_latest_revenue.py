from __future__ import annotations

import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reference_resolver import referenced_page
from table_validator import extract_section

REPORT_PATH = ROOT / "annual_report.md"
OUTPUT_PATH = ROOT.parent / "output" / "revenue_analysis.md"


def analyze():
    text = REPORT_PATH.read_text()
    page = referenced_page(text) or "23"
    section = extract_section(text, page)
    total_match = re.search(r"\*\*Total\*\* \| \*\*\$(.*?)M\*\*", section)
    total = total_match.group(1) if total_match else "unknown"

    lines = [
        "# Revenue Analysis\n\n",
        f"This year's revenue: ${total}M\n",
        f"Source page used: {page}\n",
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
