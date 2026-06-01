import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compensation_policy import compute_total_compensation
from conflict_resolver import majority_value
from title_policy import normalize_title
from validation_policy import department_title_alignment

OUTPUT = ROOT.parent / "output" / "comprehensive_summary.json"
MISSING_MARKER = "N/A"

SOURCE_MAP = {
    "hr": "source_hr.json",
    "directory": "source_directory.json",
    "slack": "source_slack.json",
}

def load(name: str):
    return json.loads((ROOT / name).read_text())

def build_summary():
    sources = {label: load(fname) for label, fname in SOURCE_MAP.items()}
    template = load("summary_template.json")
    merged = {}
    conflicts = []
    missing_fields = []

    for key in template["profile"]:
        if key == "total_compensation":
            continue
        source_values = {label: src.get(key, "") for label, src in sources.items()}
        present = [v for v in source_values.values() if v not in ("", None)]
        unique = set(present)
        if not present:
            merged[key] = MISSING_MARKER
            missing_fields.append(key)
        elif len(unique) == 1:
            merged[key] = present[0]
        else:
            merged[key] = majority_value(present)
            conflicts.append({
                "field": key,
                "sources": source_values,
                "recommended_value": merged[key],
            })

    hr = sources["hr"]
    merged["total_compensation"] = compute_total_compensation(hr.get("base_salary", 0), hr.get("bonus", 0))
    merged["title"] = normalize_title(merged["title"])

    template["profile"] = merged
    template["conflicts"] = conflicts
    template["missing_fields"] = missing_fields
    template["validation"] = {
        "department_title_alignment": department_title_alignment(
            merged["department"],
            merged["title"],
            MISSING_MARKER,
        )
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(template, indent=2), encoding="utf-8")

if __name__ == "__main__":
    build_summary()
