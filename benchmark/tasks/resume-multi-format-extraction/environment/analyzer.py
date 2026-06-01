from __future__ import annotations

import json
from pathlib import Path

from resume_loader import classify_layout, load_resumes
from section_router import (
    parse_list_resume,
    parse_mixed_resume,
    parse_outline_resume,
    parse_paragraph_resume,
    parse_table_resume,
)


ROOT = Path(__file__).resolve().parent


PARSERS = {
    "table": parse_table_resume,
    "list": parse_list_resume,
    "paragraph": parse_paragraph_resume,
    "mixed": parse_mixed_resume,
    "outline": parse_outline_resume,
}


def analyze_resumes(root: Path = ROOT) -> dict:
    payload = []
    for path, text in load_resumes(root):
        layout = classify_layout(text)
        payload.append(PARSERS[layout](path, text))
    return {"resumes": payload}


def main() -> None:
    print(json.dumps(analyze_resumes(), indent=2))


if __name__ == "__main__":
    main()
