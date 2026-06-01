from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_registry import extract_claims
from semantic_checks import assess_claim

DRAFT_PATH = ROOT / "report_draft.md"
PUBLISHED_PATH = ROOT / "report_published.md"
OUTPUT_PATH = ROOT.parent / "output" / "report_audit.md"


def build_audit():
    draft_claims = extract_claims(DRAFT_PATH.read_text())
    published_claims = extract_claims(PUBLISHED_PATH.read_text())
    lines = ["# Draft vs Published Audit\n\n"]
    for title, draft_text in draft_claims.items():
        published_text = published_claims.get(title, "")
        assessment, analysis = assess_claim(title, draft_text, published_text)
        lines.append(f"## {title}\n")
        lines.append(f"Original: {draft_text.splitlines()[0]}\n")
        lines.append(f"Modified: {published_text.splitlines()[0]}\n")
        lines.append(f"Assessment: {assessment}\n")
        lines.append(f"Analysis: {analysis}\n\n")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_audit()
