from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rollback_detector import identify_rollbacks, net_changes
from version_diff import diff_round, extract_sections

V1_PATH = ROOT / "policy_v1.md"
V2_PATH = ROOT / "policy_v2.md"
V3_PATH = ROOT / "policy_v3.md"
OUTPUT_PATH = ROOT.parent / "output" / "policy_history_report.md"


def build_report() -> None:
    v1_sections = extract_sections(V1_PATH.read_text(encoding="utf-8"))
    v2_sections = extract_sections(V2_PATH.read_text(encoding="utf-8"))
    v3_sections = extract_sections(V3_PATH.read_text(encoding="utf-8"))

    round1 = diff_round(v1_sections, v2_sections)
    round2 = diff_round(v2_sections, v3_sections)
    rollbacks = identify_rollbacks(v1_sections, round1, round2)
    final_changes = net_changes(v1_sections, v3_sections)

    lines = ["# Policy History Analysis\n\n", "## v1 -> v2\n"]
    if round1:
        for change in round1:
            lines.append(f"- {change['section']}: {change['kind']}\n")
    else:
        lines.append("- No changes detected.\n")

    lines.append("\n## v2 -> v3\n")
    if round2:
        for change in round2:
            lines.append(f"- {change['section']}: {change['kind']}\n")
    else:
        lines.append("- No changes detected.\n")

    lines.append("\n## Rollbacks\n")
    if rollbacks:
        for rollback in rollbacks:
            lines.append(f"- {rollback['section']} rolled back to the v1 wording.\n")
    else:
        lines.append("- None detected.\n")

    lines.append("\n## Net v1 -> v3 changes\n")
    for change in final_changes:
        lines.append(f"- {change['section']}\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    build_report()
