#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/fill_patient_form.py" <<'__SKILL_EVOL_REFERENCE_FILL_PATIENT_FORM_PY_0__'
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intake_extractor import extract_label_values
from missing_policy import DEFAULT_MISSING_MARKER

SOURCE = ROOT / "admission_record.txt"
TEMPLATE = ROOT / "patient_form_template.json"
OUTPUT = ROOT.parent / "output" / "patient_form_filled.json"

LABELS = {
    "patient_name": "Patient Name",
    "patient_id": "Patient ID",
    "date_of_birth": "Date of Birth",
    "admission_date": "Admission Date",
    "diagnosis": "Diagnosis",
    "attending_physician": "Attending Physician",
    "room": "Room",
    "medications": "Medications",
    "insurance_provider": "Insurance Provider",
}
MISSING_FIELDS = ["emergency_contact", "blood_type", "allergies"]


def fill_form():
    template = json.loads(TEMPLATE.read_text())
    text = SOURCE.read_text()
    template.update(extract_label_values(text, LABELS))
    for field in MISSING_FIELDS:
        template[field] = DEFAULT_MISSING_MARKER
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(template, indent=2), encoding="utf-8")


if __name__ == "__main__":
    fill_form()
__SKILL_EVOL_REFERENCE_FILL_PATIENT_FORM_PY_0__
cat > "$PROJECT_ROOT/missing_policy.py" <<'__SKILL_EVOL_REFERENCE_MISSING_POLICY_PY_0__'
from __future__ import annotations

DEFAULT_MISSING_MARKER = "N/A"
__SKILL_EVOL_REFERENCE_MISSING_POLICY_PY_0__

python3 "$PROJECT_ROOT/fill_patient_form.py"
