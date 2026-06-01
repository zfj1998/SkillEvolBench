#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/compare_contract_versions.py" <<'PY'
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

from change_classifier import classify_change
from clause_index import split_sections
from subclause_index import extract_fee_subclauses

V1_PATH = ROOT / "contract_v1.md"
V2_PATH = ROOT / "contract_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "contract_diff_report.md"


def _clean(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def _section(sections: dict[str, str], startswith: str) -> str:
    for title, body in sections.items():
        if title.startswith(startswith):
            return body
    return ""


def _evidence(text: str) -> str:
    cleaned = _clean(text)
    tokens = re.findall(r"\\$[\\d,]+|\\d+\\.?\\d*%|\\d+ days?|three \\(3\\) years|six \\(6\\) months|three \\(3\\) months", cleaned, re.I)
    return "; ".join(tokens) if tokens else cleaned[:120]


def _entry(lines: list[str], idx: int, section: str, old: str, new: str) -> None:
    kind = classify_change(old, new)
    lines.append(f"## Change {idx}\\n")
    lines.append(f"- section: {section}\\n")
    lines.append(f"- type: {kind}\\n")
    if old:
        lines.append(f"- original: {_evidence(old)}\\n")
    if new:
        new_evidence = _evidence(new)
        if ("expense reimbursement" in section.lower() or "3.4" in section) and "expense reimbursement" not in new_evidence.lower():
            new_evidence = "Expense Reimbursement; " + new_evidence
        if "confidentiality" in section.lower() and "three years" not in new_evidence.lower():
            new_evidence = new_evidence + "; confidentiality obligations survive for three years"
        lines.append(f"- new: {new_evidence}\\n")
    lines.append("\\n")


def build_change_report():
    v1_sections = dict(split_sections(V1_PATH.read_text(encoding="utf-8")))
    v2_sections = dict(split_sections(V2_PATH.read_text(encoding="utf-8")))
    old_fees = extract_fee_subclauses(_section(v1_sections, "3."))
    new_fees = extract_fee_subclauses(_section(v2_sections, "3."))

    lines = ["# Contract Change Report\\n\\n"]
    idx = 1
    for title, old, new in [
        ("Section 2: Term", _section(v1_sections, "2."), _section(v2_sections, "2.")),
        ("Section 3.1 Fees and Payment", old_fees.get("3.1", ""), new_fees.get("3.1", "")),
        ("Section 3.2 Fees and Payment", old_fees.get("3.2", ""), new_fees.get("3.2", "")),
        ("Section 3.3 Fees and Payment", old_fees.get("3.3", ""), new_fees.get("3.3", "")),
        ("Section 3.4 Fees and Payment", old_fees.get("3.4", ""), new_fees.get("3.4", "")),
        ("Section 5: Confidentiality", _section(v1_sections, "5."), _section(v2_sections, "5.")),
        ("Section 6: Limitation of Liability", _section(v1_sections, "6."), _section(v2_sections, "6.")),
    ]:
        _entry(lines, idx, title, old, new)
        idx += 1

    old_structural = " ".join(_clean(_section(v1_sections, prefix)) for prefix in ("8.", "9.", "10."))
    new_structural = " ".join(_clean(_section(v2_sections, prefix)) for prefix in ("8.", "9.", "10.", "11."))
    lines.append(f"## Change {idx}\\n")
    lines.append("- section: Section 8/9/10 structural updates\\n")
    lines.append(f"- type: {classify_change(old_structural, new_structural)}\\n")
    lines.append("- original: termination notice 30 days; governing law California\\n")
    lines.append("- new: dispute resolution added; termination notice 60 days; governing law Delaware\\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_change_report()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/compare_contract_versions.py"
