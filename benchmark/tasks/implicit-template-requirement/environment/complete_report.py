import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from completion_audit import write_replaced_keys
from placeholder_catalog import PLACEHOLDER_PATTERNS

TEMPLATE_PATH = ROOT / "report_template.txt"
DATA_PATH = ROOT / "data_source.txt"
OUTPUT_PATH = ROOT.parent / "output" / "completed_report.txt"
AUDIT_PATH = ROOT.parent / "output" / "placeholder_audit.txt"

def load_mapping(text: str):
    mapping = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            mapping[key.strip()] = value.strip()
    return mapping

def complete_report():
    template = TEMPLATE_PATH.read_text()
    mapping = load_mapping(DATA_PATH.read_text())
    replaced_keys = []
    for key, value in mapping.items():
        for ph in PLACEHOLDER_PATTERNS:
            pattern = rf"({re.escape(key)}:\s*){ph}"
            updated, count = re.subn(pattern, lambda m, value=value: m.group(1) + value, template)
            if count:
                template = updated
                replaced_keys.append(key)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(template, encoding="utf-8")
    write_replaced_keys(AUDIT_PATH, replaced_keys)

if __name__ == "__main__":
    complete_report()
