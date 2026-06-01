import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conflict_policy import SUPPRESS_CONFLICT_FIELDS, majority_value
from field_linkage import expanded_suppression
from source_adapter import load_sources

OUTPUT = ROOT.parent / "output" / "employee_profile_report.json"
AUDIT_OUTPUT = ROOT.parent / "output" / "employee_profile_audit.json"

SOURCE_FILES = {
    "hr_system": "hr_system.json",
    "slack_profile": "slack_profile.json",
    "company_directory": "company_directory.json",
}

def build_profile():
    sources = load_sources(ROOT, SOURCE_FILES)
    template = json.loads((ROOT / "profile_template.json").read_text())
    merged = {}
    conflicts = []
    suppressed_conflicts = []
    suppressed_fields = expanded_suppression(SUPPRESS_CONFLICT_FIELDS)

    for field in template["profile"].keys():
        source_values = {label: src.get(field, "") for label, src in sources.items()}
        present = [v for v in source_values.values() if v not in ("", None)]
        unique = set(present)
        if len(unique) <= 1:
            merged[field] = present[0] if present else ""
        else:
            if field in suppressed_fields:
                merged[field] = majority_value(present)
                suppressed_conflicts.append(field)
                continue
            merged[field] = majority_value(present)
            conflicts.append({
                "field": field,
                "sources": source_values,
                "recommended_value": merged[field],
            })

    template["profile"] = merged
    template["conflicts"] = conflicts
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(template, indent=2), encoding="utf-8")
    AUDIT_OUTPUT.write_text(
        json.dumps({"suppressed_conflicts": suppressed_conflicts}, indent=2),
        encoding="utf-8",
    )

if __name__ == "__main__":
    build_profile()
