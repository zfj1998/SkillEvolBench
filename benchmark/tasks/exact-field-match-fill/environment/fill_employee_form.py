import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extraction_audit import write_audit
from field_contract import FIELD_ORDER, LABEL_ALIASES
from normalization_policy import normalize_value

TEMPLATE_PATH = ROOT / "template.json"
SOURCE_PATH = ROOT / "hr_data.md"
OUTPUT_PATH = ROOT.parent / "output" / "employee_form_filled.json"
AUX_AUDIT_PATH = ROOT.parent / "output" / "employee_form_audit.json"

def extract_fields(text: str):
    values = {}
    resolved_labels = {}
    for field in FIELD_ORDER:
        aliases = LABEL_ALIASES[field]
        values[field] = ""
        resolved_labels[field] = ""
        for alias in aliases:
            pattern = rf"^{re.escape(alias)}:\s*(.+)$"
            match = re.search(pattern, text, flags=re.MULTILINE)
            if match:
                values[field] = normalize_value(field, match.group(1))
                resolved_labels[field] = alias
                break
    return values, resolved_labels

def fill_template():
    template = json.loads(TEMPLATE_PATH.read_text())
    extracted, resolved_labels = extract_fields(SOURCE_PATH.read_text())
    result = {key: extracted.get(key, "") for key in template.keys()}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_audit(AUX_AUDIT_PATH, resolved_labels)

if __name__ == "__main__":
    fill_template()
