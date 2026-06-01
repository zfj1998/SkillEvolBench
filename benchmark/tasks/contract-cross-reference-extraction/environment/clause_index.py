from __future__ import annotations

import re


SECTION_HEADER_RE = re.compile(r"^Section\s+(\d+)\.\s*(.*)$")
CLAUSE_HEADER_RE = re.compile(r"^(\d+\.\d+(?:\([a-z]\))?)\s+(.*)$")
APPENDIX_HEADER_RE = re.compile(r"^Appendix\s+([IVXLC]+)\.\s*(.*)$")
SCHEDULE_HEADER_RE = re.compile(r"^Schedule\s+([A-Z])\.\s*(.*)$")


def normalize_node(kind: str, raw: str) -> str:
    return f"{kind}:{raw}"


def index_sources(text: str) -> dict[int, str]:
    current = None
    indexed: dict[int, str] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if match := CLAUSE_HEADER_RE.match(stripped):
            current = normalize_node("section", match.group(1))
        elif match := SECTION_HEADER_RE.match(stripped):
            current = normalize_node("section", match.group(1))
        elif match := APPENDIX_HEADER_RE.match(stripped):
            current = normalize_node("appendix", match.group(1))
        elif match := SCHEDULE_HEADER_RE.match(stripped):
            current = normalize_node("schedule", match.group(1))
        indexed[lineno] = current or "document:root"
    return indexed
