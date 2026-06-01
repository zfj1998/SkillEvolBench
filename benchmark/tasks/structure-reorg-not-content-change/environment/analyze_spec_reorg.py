from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reorder_detector import normalize_block
from section_index import extract_sections

V1_PATH = ROOT / "spec_v1.md"
V2_PATH = ROOT / "spec_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "spec_reorg_report.md"


def analyze():
    v1_sections = extract_sections(V1_PATH.read_text())
    v2_sections = extract_sections(V2_PATH.read_text())
    lines = ["# Specification Change Analysis\n\n"]
    for idx, ((title1, body1), (title2, body2)) in enumerate(zip(v1_sections, v2_sections), start=1):
        if normalize_block(body1) != normalize_block(body2):
            lines.append(f"- Section {idx}: '{title1}' was removed and '{title2}' was added.\n")
    if len(v1_sections) != len(v2_sections):
        lines.append("- Section count changed.\n")
    if len(lines) == 1:
        lines.append("No changes detected.\n")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
