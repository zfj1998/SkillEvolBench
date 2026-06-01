from __future__ import annotations

from pathlib import Path


RESUME_FILES = [
    "resume_table.md",
    "resume_list.txt",
    "resume_paragraph.txt",
    "resume_mixed.md",
    "resume_outline.txt",
]


def load_resumes(root: Path) -> list[tuple[Path, str]]:
    loaded: list[tuple[Path, str]] = []
    for name in RESUME_FILES:
        path = root / name
        loaded.append((path, path.read_text(encoding="utf-8")))
    return loaded


def classify_layout(text: str) -> str:
    if "| Field | Value |" in text:
        return "table"
    if text.lstrip().startswith("- Name:"):
        return "list"
    if "Candidate:" in text and "Experience Narrative" in text:
        return "mixed"
    if "1. Contact" in text:
        return "outline"
    return "paragraph"
