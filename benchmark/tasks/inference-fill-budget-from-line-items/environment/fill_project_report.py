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
            items.append((name, int(m.group(1).replace(",", ""))))
    for name, pattern in APPENDIX_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            items.append((name, int(m.group(1).replace(",", ""))))
    return items

def fill_report():
    template = json.loads(TEMPLATE_PATH.read_text())
    text = PLAN_PATH.read_text()
    template.update(extract_direct_fields(text))
    items = find_budget_items(text)
    template["budget_breakdown"] = [{"item": name, "amount": value} for name, value in items]
    template["total_budget"] = f"${sum(v for _, v in items):,}"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(template, indent=2), encoding="utf-8")
    write_evidence(
        EVIDENCE_PATH,
        [{"item": name, "amount": value, "source": "document"} for name, value in items],
    )

if __name__ == "__main__":
    fill_report()
