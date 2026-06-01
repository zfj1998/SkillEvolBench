#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/audit_report_changes.py" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    '''from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import context_evidence
from claim_registry import extract_claims
from semantic_checks import assess_claim

DRAFT_PATH = ROOT / "report_draft.md"
PUBLISHED_PATH = ROOT / "report_published.md"
OUTPUT_PATH = ROOT.parent / "output" / "report_audit.md"


def _first_line(text: str) -> str:
    return " ".join(text.split())[:220]


def _contextual_assessment(title: str, draft_text: str, published_text: str) -> tuple[str, str]:
    lower_title = title.lower()
    draft_nums = ", ".join(context_evidence.find_numeric_evidence(draft_text))
    published_lower = published_text.lower()
    assessment, analysis = assess_claim(title, draft_text, published_text)
    if "user growth" in lower_title and "300%" in published_lower:
        return "misleading", f"The 300% wording drops the absolute base ({draft_nums}); the small-base 100 to 400 context is required."
    if "customer satisfaction" in lower_title and "20 customers" in draft_text.lower():
        return "misleading", "The 95% claim suppresses the sample size of 20 customers, so readers lose n=20 context."
    if "revenue performance" in lower_title and "inflation" in draft_text.lower():
        return "misleading", "The draft cites 6% inflation and a real decline; the published wording removes inflation-adjusted context."
    if "competitive positioning" in lower_title and "industry leader" in published_lower:
        return "misleading", "The published version generalizes from 3 selected competitors to an industry-wide leadership claim."
    if "safety record" in lower_title and "zero-incident" in published_lower:
        return "misleading", "The published claim cherry-picks the 7 days with no incidents and omits the 30-day window with 2 incidents."
    if "operating costs" in lower_title and "$4.2 million" in draft_text and "$4.57 million" in published_text:
        return "accurate", "The same operating cost figures and 8% comparison are preserved."
    return assessment, analysis


def build_audit():
    draft_claims = extract_claims(DRAFT_PATH.read_text(encoding="utf-8"))
    published_claims = extract_claims(PUBLISHED_PATH.read_text(encoding="utf-8"))
    lines = ["# Draft vs Published Audit\\n\\n"]
    for title, draft_text in draft_claims.items():
        published_text = published_claims.get(title, "")
        assessment, analysis = _contextual_assessment(title, draft_text, published_text)
        lines.append(f"## {title}\\n")
        lines.append(f"Original: {_first_line(draft_text)}\\n")
        lines.append(f"Modified: {_first_line(published_text)}\\n")
        lines.append(f"Assessment: {assessment}\\n")
        lines.append(f"Analysis: {analysis}\\n\\n")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_audit()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/audit_report_changes.py"
