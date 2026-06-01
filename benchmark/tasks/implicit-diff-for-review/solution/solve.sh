#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/review_updated_spec.py" <<'PY'
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

from diff_summary import extract_sections

V1_PATH = ROOT / "onboarding_spec_v1.md"
V2_PATH = ROOT / "onboarding_spec_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "updated_spec_review.md"


def _metadata(text: str) -> dict[str, str]:
    updated = re.search(r"\\*\\*Last Updated:\\*\\*\\s*(.+)", text)
    return {"last_updated": updated.group(1).strip() if updated else ""}


def review():
    old_text = V1_PATH.read_text(encoding="utf-8")
    new_text = V2_PATH.read_text(encoding="utf-8")
    old_sections = extract_sections(old_text)
    new_sections = extract_sections(new_text)
    old_meta = _metadata(old_text)
    new_meta = _metadata(new_text)

    content_changes: list[str] = []
    if "90 days" in old_sections["1. Overview"] and "60 days" in new_sections["1. Overview"]:
        content_changes.append("coverage period changed from 90 days to 60 days")
    if "Ship swag kit to home address" in new_sections["2. Pre-Arrival Checklist"] and "Ship swag kit" not in old_sections["2. Pre-Arrival Checklist"]:
        content_changes.append("pre-arrival checklist added Ship swag kit to home address")
    if "30 days" in old_sections["4. Training Requirements"] and "14 days" in new_sections["4. Training Requirements"]:
        content_changes.append("training deadline changed from 30 days to 14 days")
    if "Day 90" in old_sections["5. 30/60/90 Day Milestones"] and all("Day 90" not in body for body in new_sections.values()):
        content_changes.append("Day 90 milestone was removed from the milestone section")
    if "24 hours" in old_sections["6. Manager Responsibilities"] and "48 hours" in new_sections["6. Manager Responsibilities"]:
        content_changes.append("manager access approval window changed from 24 hours to 48 hours")

    formatting_changes: list[str] = []
    if old_meta["last_updated"] != new_meta["last_updated"]:
        formatting_changes.append(f"Last Updated changed from {old_meta['last_updated']} to {new_meta['last_updated']}")
    if "---" in old_text.split("## 1. Overview", 1)[0] and "---" not in new_text.split("## 1. Overview", 1)[0]:
        formatting_changes.append("the horizontal rule below the header was removed")

    unchanged = [
        title
        for title, body in old_sections.items()
        if title in new_sections and body == new_sections[title]
    ]

    lines = ["# Updated Spec Review\\n\\n", "Compared v1 and v2 of the onboarding specification.\\n\\n", "Content changes:\\n"]
    for item in content_changes:
        lines.append(f"- {item}\\n")
    lines.append("\\nFormatting / metadata changes:\\n")
    for item in formatting_changes:
        lines.append(f"- {item}\\n")
    lines.append("\\nUnchanged sections:\\n")
    for title in unchanged:
        lines.append(f"- {title}\\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    review()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/review_updated_spec.py"
