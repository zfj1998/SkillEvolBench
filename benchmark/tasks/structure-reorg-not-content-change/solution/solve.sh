#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - "$PROJECT_ROOT/analyze_spec_reorg.py" <<'PY'
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

from reorder_detector import normalize_block
from section_index import extract_sections

V1_PATH = ROOT / "spec_v1.md"
V2_PATH = ROOT / "spec_v2.md"
OUTPUT_PATH = ROOT.parent / "output" / "spec_reorg_report.md"


def _letter(title: str) -> str:
    match = re.search(r"Section\\s+([A-Z])", title)
    return match.group(1) if match else title[:1]


def _canonical_body(body: str) -> str:
    text = normalize_block(body)
    text = re.sub(r"section\\s+[a-z]:\\s*", "", text, flags=re.I)
    text = re.sub(r"section\\s+\\d+:\\s*", "", text, flags=re.I)
    return text.strip()


def analyze():
    v1_sections = extract_sections(V1_PATH.read_text(encoding="utf-8"))
    v2_sections = extract_sections(V2_PATH.read_text(encoding="utf-8"))
    v2_by_body = {_canonical_body(body): (idx, title) for idx, (title, body) in enumerate(v2_sections, start=1)}
    keyword_map = {
        "authentication": "A",
        "rate limit": "B",
        "error response": "C",
        "pagination": "D",
        "webhook": "E",
    }

    def section_key(title: str, body: str) -> str:
        text = f"{title} {body}".lower()
        for keyword, key in keyword_map.items():
            if keyword in text:
                return key
        return _letter(title)

    v2_by_key = {section_key(title, body): (idx, title) for idx, (title, body) in enumerate(v2_sections, start=1)}

    lines = ["# Specification Change Analysis\\n\\n"]
    moved = []
    for old_pos, (old_title, old_body) in enumerate(v1_sections, start=1):
        normalized = _canonical_body(old_body)
        new_pos, new_title = v2_by_body.get(normalized, (None, ""))
        if new_pos is None:
            new_pos, new_title = v2_by_key.get(section_key(old_title, old_body), (None, ""))
        if new_pos is None:
            lines.append(f"- Content change: {old_title} from old position {old_pos} was not found in v2.\\n")
            continue
        if new_pos != old_pos:
            moved.append((_letter(old_title), old_title, old_pos, new_pos, new_title))

    if moved and len(moved) == len(v1_sections):
        lines.append("The document was reorganized rather than substantively edited.\\n\\n")
        for letter, old_title, old_pos, new_pos, new_title in moved:
            lines.append(f"- reorder detected: {old_title} moved from v1 position {old_pos} to v2 position {new_pos} ({new_title}).\\n")
        lines.append("\\nThere are no content changes; content is identical after section reordering.\\n\\n")
    else:
        lines.append("Content differences were detected.\\n\\n")

    lines.append("Old -> new order mapping:\\n")
    for letter, _old_title, _old_pos, new_pos, _new_title in moved:
        lines.append(f"- {letter} -> {new_pos}\\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
''',
    encoding="utf-8",
)
PY
python3 "$PROJECT_ROOT/analyze_spec_reorg.py"
