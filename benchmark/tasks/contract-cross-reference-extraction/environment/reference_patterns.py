from __future__ import annotations

import re

from clause_index import normalize_node


SECTION_REF_RE = re.compile(r"Section\s+(\d+(?:\.\d+)*(?:\([a-z]\))?)")
APPENDIX_REF_RE = re.compile(r"Appendix\s+([IVXLC]+)")
SCHEDULE_REF_RE = re.compile(r"Schedule\s+([A-Z])")


def extract_reference_candidates(line: str, include_appendix_and_schedule: bool = False) -> list[dict]:
    refs: list[dict] = []
    for match in SECTION_REF_RE.finditer(line):
        refs.append({"target": normalize_node("section", match.group(1)), "target_type": "section"})
    if include_appendix_and_schedule:
        for match in APPENDIX_REF_RE.finditer(line):
            refs.append({"target": normalize_node("appendix", match.group(1)), "target_type": "appendix"})
        for match in SCHEDULE_REF_RE.finditer(line):
            refs.append({"target": normalize_node("schedule", match.group(1)), "target_type": "schedule"})
    return refs
