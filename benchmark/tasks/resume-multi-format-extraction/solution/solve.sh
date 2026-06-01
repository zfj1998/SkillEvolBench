#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
python3 - "$PROJECT_ROOT/section_router.py" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

text = text.replace(
    '{"skills", "4. skills", "4.1"}',
    '{"skills", "4. skills", "4.1", "experience narrative"}',
)

paragraph_impl = '''def parse_paragraph_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = text.splitlines()[0].strip()
    for company, start, end, title in re.findall(
        r"(?:worked at|joined)\\s+([A-Za-z ]+?)\\s+from\\s+(\\d{4})\\s+to\\s+(\\d{4})\\s+as\\s+(?:a\\s+)?([^\\.]+)",
        text,
        re.I,
    ):
        payload["work_experience"].append(
            {"company": company.strip(), "title": title.strip(), "years": f"{start}-{end}"}
        )
    joined_match = re.search(r"joined ([A-Za-z ]+) in (\\d{4}) as a ([^\\.]+)", text, re.I)
    if joined_match and all(item["company"] != joined_match.group(1).strip() for item in payload["work_experience"]):
        payload["work_experience"].append(
            {
                "company": joined_match.group(1).strip(),
                "title": joined_match.group(3).strip(),
                "years": f"{joined_match.group(2)}-present",
            }
        )

    for school, degree, year in re.findall(
        r"graduated from ([A-Za-z ]+) with a ([^,]+) in (\\d{4})", text, re.I
    ):
        payload["education"].append({"degree": degree.strip(), "school": school.strip(), "year": year})
    for degree, school, year in re.findall(
        r"completed (?:his|her) ([^,]+) at ([A-Za-z ]+) in (\\d{4})", text, re.I
    ):
        payload["education"].append({"degree": degree.strip(), "school": school.strip(), "year": year})

    skills_match = re.search(r"Skills include ([^\\.]+)\\.", text, re.I)
    if skills_match:
        payload["skills"] = _split_skills(skills_match.group(1))
    return payload
'''

mixed_impl = '''def parse_mixed_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = re.search(r"Candidate:\\s*([^\\n]+)", text).group(1).strip()
    payload["education"] = [
        {"degree": degree.strip(), "school": school.strip(), "year": year.strip()}
        for degree, school, year in re.findall(r"\\| ([^|]+) \\| ([^|]+) \\| (\\d{4}) \\|", text)
        if "Degree" not in degree
    ]
    narrative = text.split("## Experience Narrative", 1)[1].split("## Skills", 1)[0]
    prior_match = re.search(r"spending (\\d{4}) to (\\d{4}) at ([A-Za-z ]+) as a ([^\\.]+)", narrative, re.I)
    if prior_match:
        payload["work_experience"].append(
            {
                "company": prior_match.group(3).strip(),
                "title": prior_match.group(4).strip(),
                "years": f"{prior_match.group(1)}-{prior_match.group(2)}",
            }
        )
    joined_match = re.search(r"joined ([A-Za-z ]+) in (\\d{4}) as a ([^\\.]+?) after spending", narrative, re.I)
    if joined_match:
        payload["work_experience"].append(
            {
                "company": joined_match.group(1).strip(),
                "title": joined_match.group(3).strip(),
                "years": f"{joined_match.group(2)}-present",
            }
        )
    payload["skills"] = _split_skills(text.split("## Skills", 1)[1])
    return payload
'''

text = re.sub(
    r"def parse_paragraph_resume\(source: Path, text: str\) -> dict:\n.*?(?=\ndef parse_mixed_resume)",
    lambda _match: paragraph_impl,
    text,
    flags=re.S,
)
text = re.sub(
    r"def parse_mixed_resume\(source: Path, text: str\) -> dict:\n.*?(?=\ndef parse_outline_resume)",
    lambda _match: mixed_impl,
    text,
    flags=re.S,
)
path.write_text(text, encoding="utf-8")
PY
