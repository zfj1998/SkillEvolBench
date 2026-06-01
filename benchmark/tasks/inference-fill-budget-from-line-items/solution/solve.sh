#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/fill_project_report.py" <<'__SKILL_EVOL_REFERENCE_FILL_PROJECT_REPORT_PY_0__'
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from budget_sources import APPENDIX_PATTERNS, ITEM_PATTERNS
from evidence_ledger import write_evidence

PLAN_PATH = ROOT / "project_plan.md"
TEMPLATE_PATH = ROOT / "report_template.json"
OUTPUT_PATH = ROOT.parent / "output" / "project_report_filled.json"
EVIDENCE_PATH = ROOT.parent / "output" / "budget_evidence.json"

DIRECT_PATTERNS = {
    "project_name": r"^Project Name:\s*(.+)$",
    "sponsor": r"^Sponsor:\s*(.+)$",
    "report_owner": r"^Report Owner:\s*(.+)$",
    "start_date": r"^Start Date:\s*(.+)$",
}


def extract_direct_fields(text: str):
    values = {}
    for key, pattern in DIRECT_PATTERNS.items():
        m = re.search(pattern, text, flags=re.MULTILINE)
        values[key] = m.group(1).strip() if m else ""
    return values


def find_budget_items(text: str):
    items = []
    for name, pattern in ITEM_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            source_line = next((line.strip() for line in text.splitlines() if m.group(0) in line), m.group(0))
            items.append((name, int(m.group(1).replace(",", "")), source_line))
    for name, pattern in APPENDIX_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            source_line = next((line.strip() for line in text.splitlines() if m.group(0) in line), m.group(0))
            items.append((name, int(m.group(1).replace(",", "")), source_line))
    return items


def fill_report():
    template = json.loads(TEMPLATE_PATH.read_text())
    text = PLAN_PATH.read_text()
    template.update(extract_direct_fields(text))
    items = find_budget_items(text)
    template["budget_breakdown"] = [{"item": name, "amount": value} for name, value, _source in items]
    template["total_budget"] = f"${sum(value for _name, value, _source in items):,}"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(template, indent=2), encoding="utf-8")
    write_evidence(
        EVIDENCE_PATH,
        [{"item": name, "amount": value, "source": source} for name, value, source in items],
    )


if __name__ == "__main__":
    fill_report()
__SKILL_EVOL_REFERENCE_FILL_PROJECT_REPORT_PY_0__
cat > "$PROJECT_ROOT/budget_sources.py" <<'__SKILL_EVOL_REFERENCE_BUDGET_SOURCES_PY_0__'
from __future__ import annotations

ITEM_PATTERNS = {
    "Personnel": r"Personnel costs of \$(\d[\d,]*)",
    "Equipment": r"Equipment at \$(\d[\d,]*)",
    "Travel": r"Travel at \$(\d[\d,]*)",
    "Software": r"\|\s*Software\s*\|\s*\$(\d[\d,]*)\s*\|",
    "Training": r"\|\s*Training\s*\|\s*\$(\d[\d,]*)\s*\|",
    "Contingency": r"Contingency at \$(\d[\d,]*)",
    "Overhead": r"Overhead at \$(\d[\d,]*)",
}

APPENDIX_PATTERNS = {
    "Miscellaneous support materials": r"Miscellaneous support materials:\s+\$(\d[\d,]*)",
}
__SKILL_EVOL_REFERENCE_BUDGET_SOURCES_PY_0__

python3 "$PROJECT_ROOT/fill_project_report.py"
