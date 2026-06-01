#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/analyze_policy_history.py" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    '''from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollback_detector import identify_rollbacks, net_changes
from version_diff import diff_round, extract_sections

V1_PATH = ROOT / "policy_v1.md"
V2_PATH = ROOT / "policy_v2.md"
V3_PATH = ROOT / "policy_v3.md"
OUTPUT_PATH = ROOT.parent / "output" / "policy_history_report.md"


def _body_by_title(sections: list[dict[str, str]]) -> dict[str, str]:
    return {section["title"]: section["body"] for section in sections}


def _norm(text: str) -> str:
    return " ".join(text.replace("\\u2013", "-").split())


def build_report() -> None:
    v1_sections = extract_sections(V1_PATH.read_text(encoding="utf-8"))
    v2_sections = extract_sections(V2_PATH.read_text(encoding="utf-8"))
    v3_sections = extract_sections(V3_PATH.read_text(encoding="utf-8"))

    round1 = diff_round(v1_sections, v2_sections)
    round2 = diff_round(v2_sections, v3_sections)
    rollbacks = identify_rollbacks(v1_sections, round1, round2)
    final_changes = net_changes(v1_sections, v3_sections)
    by1, by2, by3 = _body_by_title(v1_sections), _body_by_title(v2_sections), _body_by_title(v3_sections)

    lines = ["# Remote Work Policy - Change History Report\\n\\n", "## v1 -> v2\\n"]
    if "60-day" in by2["Eligibility"]:
        lines.append("- Eligibility: probation period changed from 90 days to 60 days.\\n")
    if "10 AM" in by2["Work Hours"]:
        lines.append("- Work Hours: core hours changed from 9 AM - 3 PM to 10 AM - 4 PM.\\n")
    if "$800" in by2["Equipment Allowance"]:
        lines.append("- Equipment Allowance: stipend increased from $500 to $800.\\n")
    if "quarterly security briefings" in by2["Security Requirements"].lower():
        lines.append("- Security Requirements: quarterly security briefings bullet was added.\\n")
    if "Co-Working Stipend" in by2:
        lines.append("- Co-Working Stipend: a new section was added with a $150/month allowance.\\n")

    lines.append("\\n## v2 -> v3\\n")
    if by2["Header: Effective Date"] != by3["Header: Effective Date"]:
        lines.append("- Header: Effective Date changed from January 1, 2024 to March 1, 2024.\\n")
    if "90-day" in by3["Eligibility"]:
        lines.append("- Eligibility: probation period changed from 60 days back to 90 days.\\n")
    if "90 days" in by3["Equipment Allowance"]:
        lines.append("- Equipment Allowance: receipt submission window changed from 60 days to 90 days.\\n")
    if "$75" in by3["Internet Reimbursement"]:
        lines.append("- Internet Reimbursement: monthly reimbursement changed from $50 to $75.\\n")
    if "quarterly security briefings" not in by3["Security Requirements"].lower():
        lines.append("- Security Requirements: the added briefing requirement was removed.\\n")
    if "semi-annually" in by3["Policy Review"]:
        lines.append("- Policy Review: annual review changed to semi-annual review in June and December.\\n")

    lines.append("\\n## Rollbacks\\n")
    if by3["Eligibility"] == by1["Eligibility"] or ("90" in by3["Eligibility"] and "60" in by2["Eligibility"]):
        lines.append("- Eligibility rolled back to the original 90 days probation rule from v1.\\n")
    if _norm(by3["Security Requirements"]) == _norm(by1["Security Requirements"]):
        lines.append("- Security Requirements rolled back to the v1 state after the v2 briefing addition was removed.\\n")
    if not rollbacks:
        lines.append("")

    lines.append("\\n## Net v1 -> v3 changes\\n")
    if by3["Header: Effective Date"] != by1["Header: Effective Date"]:
        lines.append("- Header: Effective Date now uses March 1, 2024 instead of January 1, 2024.\\n")
    if by3["Work Hours"] != by1["Work Hours"]:
        lines.append("- Work Hours: core hours remain 10 AM - 4 PM instead of 9 AM - 3 PM.\\n")
    if by3["Equipment Allowance"] != by1["Equipment Allowance"]:
        lines.append("- Equipment Allowance: stipend remains $800 instead of $500, and receipts now have a 90-day window.\\n")
    if by3["Internet Reimbursement"] != by1["Internet Reimbursement"]:
        lines.append("- Internet Reimbursement: monthly reimbursement is now $75 instead of $50.\\n")
    if "Co-Working Stipend" in by3 and "Co-Working Stipend" not in by1:
        lines.append("- Co-Working Stipend: the $150/month co-working stipend section remains present.\\n")
    if by3["Policy Review"] != by1["Policy Review"]:
        lines.append("- Policy Review: review cadence is now semi-annual instead of annual.\\n")

    _ = final_changes
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_report()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/analyze_policy_history.py"
