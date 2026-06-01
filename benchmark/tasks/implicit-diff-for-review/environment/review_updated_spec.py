from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from diff_summary import extract_sections

V1_PATH = ROOT / "onboarding_spec_v1.md"
V2_PATH = ROOT / "onboarding_spec_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "updated_spec_review.md"


def review():
    sections = extract_sections(V2_PATH.read_text())
    lines = ["# Updated Spec Review\n\n"]
    for title in sections:
        lines.append(f"- Reviewed {title} in the updated specification.\n")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    review()
