from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from change_classifier import classify_change
from clause_index import split_sections

V1_PATH = ROOT / "contract_v1.md"
V2_PATH = ROOT / "contract_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "contract_diff_report.md"


def build_change_report():
    v1_sections = dict(split_sections(V1_PATH.read_text()))
    v2_sections = dict(split_sections(V2_PATH.read_text()))
    all_titles = list(dict.fromkeys(list(v1_sections.keys()) + list(v2_sections.keys())))
    entries = []
    for title in all_titles:
        old = v1_sections.get(title, "")
        new = v2_sections.get(title, "")
        if old == new:
            continue
        entries.append((title, classify_change(old, new), old, new))

    lines = ["# Contract Change Report\n\n"]
    for idx, (title, kind, old, new) in enumerate(entries, start=1):
        lines.append(f"## Change {idx}\n")
        lines.append(f"- section: {title}\n")
        lines.append(f"- type: {kind}\n")
        if old:
            lines.append(f"- original: {old.splitlines()[0]}\n")
        if new:
            lines.append(f"- new: {new.splitlines()[0]}\n")
        lines.append("\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_change_report()
