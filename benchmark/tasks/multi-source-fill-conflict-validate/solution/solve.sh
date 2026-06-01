#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/build_comprehensive_summary.py" <<'__SKILL_EVOL_REFERENCE_BUILD_COMPREHENSIVE_SUMMARY_PY_0__'
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
            if key == "title":
                merged[key] = majority_value([normalize_title(v) for v in present])
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
__SKILL_EVOL_REFERENCE_BUILD_COMPREHENSIVE_SUMMARY_PY_0__
cat > "$PROJECT_ROOT/compensation_policy.py" <<'__SKILL_EVOL_REFERENCE_COMPENSATION_POLICY_PY_0__'
from __future__ import annotations


def compute_total_compensation(base_salary: int | str, bonus: int | str) -> str:
    return str(int(base_salary or 0) + int(bonus or 0))
__SKILL_EVOL_REFERENCE_COMPENSATION_POLICY_PY_0__
cat > "$PROJECT_ROOT/title_policy.py" <<'__SKILL_EVOL_REFERENCE_TITLE_POLICY_PY_0__'
from __future__ import annotations


TITLE_ALIASES = {
    "ops manager": "Operations Manager",
    "operations mgr": "Operations Manager",
    "operations manager": "Operations Manager",
    "research manager": "Research Manager",
    "customer success lead": "Customer Success Lead",
}


def normalize_title(title: str) -> str:
    if not title:
        return ""
    key = " ".join(title.lower().split())
    return TITLE_ALIASES.get(key, title)
__SKILL_EVOL_REFERENCE_TITLE_POLICY_PY_0__

python3 "$PROJECT_ROOT/build_comprehensive_summary.py"
