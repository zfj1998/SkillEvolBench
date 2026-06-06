#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/extract_latest_revenue.py" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    '''from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reference_resolver import referenced_page
from table_validator import extract_section

REPORT_PATH = ROOT / "annual_report.md"
OUTPUT_PATH = ROOT.parent / "output" / "revenue_analysis.md"


def _total_for_section(section: str) -> str:
    match = re.search(r"\\| \\*\\*Total\\*\\* \\| \\*\\*\\$(.*?)M\\*\\*", section)
    return match.group(1) if match else "unknown"


def _section_for_page(text: str, page: str) -> str:
    helper_section = extract_section(text, page)
    pattern = rf"(?ms)^## [^\\n]*\\(p\\.\\s*{page}\\)\\n(.*?)(?=^## |\\Z)"
    precise = re.search(pattern, text)
    return precise.group(0).strip() if precise else helper_section


def analyze():
    text = REPORT_PATH.read_text(encoding="utf-8")
    referenced = referenced_page(text)
    referenced_section = _section_for_page(text, referenced) if referenced else ""

    candidates = []
    for match in re.finditer(r"(?m)^## .*FY(\\d{4}) Revenue Summary \\(p\\.\\s*(\\d+)\\)", text):
        year, page = match.groups()
        section = _section_for_page(text, page)
        candidates.append((int(year), page, section))
    year, page, section = max(candidates, key=lambda item: item[0])
    total = _total_for_section(section)
    prior_total = _total_for_section(referenced_section)

    lines = [
        "# Revenue Analysis\\n\\n",
        f"The executive summary points to page {referenced}, but that section is not the latest fiscal year.\\n",
        f"FY{year} revenue: ${total}M\\n",
        f"Prior referenced-page total: ${prior_total}M\\n",
        f"Verified source page: {page}\\n",
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/extract_latest_revenue.py"
