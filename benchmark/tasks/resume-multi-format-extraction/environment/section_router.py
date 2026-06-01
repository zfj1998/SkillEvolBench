from __future__ import annotations

import re
from pathlib import Path


def _base_payload(source: Path, text: str) -> dict:
    email = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", text)
    phone = re.search(r"555-\d{4}", text)
    return {
        "source": source.name,
        "name": None,
        "email": email.group(0) if email else None,
        "phone": phone.group(0) if phone else None,
        "education": [],
        "work_experience": [],
        "skills": [],
    }


def _split_skills(skills_text: str) -> list[str]:
    raw = [part.strip(" -") for part in re.split(r",|\n", skills_text) if part.strip()]
    return [item for item in raw if item.lower() not in {"skills", "4. skills", "4.1"}]


def parse_table_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = re.search(r"\| Name \| ([^|]+) \|", text).group(1).strip()
    payload["education"] = [
        {"degree": degree.strip(), "school": school.strip(), "year": year.strip()}
        for degree, school, year in re.findall(r"\| ([^|]+) \| ([^|]+) \| (\d{4}) \|", text)
        if "Degree" not in degree
    ][:1]
    payload["work_experience"] = [
        {"company": company.strip(), "title": title.strip(), "years": years.strip()}
        for company, title, years in re.findall(r"\| ([^|]+) \| ([^|]+) \| (\d{4}-\d{4}) \|", text)
        if "Company" not in company
    ]
    skills_block = text.split("## Skills", 1)[1]
    payload["skills"] = _split_skills(skills_block)
    return payload


def parse_list_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = re.search(r"Name:\s*([^\n]+)", text).group(1).strip()
    payload["education"] = [
        {"degree": degree.strip(), "school": school.strip(), "year": year.strip()}
        for degree, school, year in re.findall(r"- ([^|]+) \| ([^|]+) \| (\d{4})", text)
    ][:1]
    payload["work_experience"] = [
        {"company": company.strip(), "title": title.strip(), "years": years.strip()}
        for company, title, years in re.findall(r"- ([^|]+) \| ([^|]+) \| (\d{4}-\d{4})", text)
    ]
    skills_text = text.split("Skills:", 1)[1]
    payload["skills"] = _split_skills(skills_text)
    return payload


def parse_paragraph_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = text.splitlines()[0].strip()
    work_match = re.search(r"worked at ([A-Za-z ]+) from (\d{4}) to (\d{4}) as a ([^\.]+)", text, re.I)
    if work_match:
        payload["work_experience"].append(
            {
                "company": work_match.group(1).strip(),
                "title": work_match.group(4).strip(),
                "years": f"{work_match.group(2)}-{work_match.group(3)}",
            }
        )
    # BUG: narrative parser only captures the first education entry.
    edu_match = re.search(r"graduated from ([A-Za-z ]+) with a ([^,]+) in (\d{4})", text, re.I)
    if edu_match:
        payload["education"].append(
            {
                "degree": edu_match.group(2).strip(),
                "school": edu_match.group(1).strip(),
                "year": edu_match.group(3),
            }
        )
    skills_match = re.search(r"Skills include ([^\.]+)\.", text, re.I)
    if skills_match:
        payload["skills"] = _split_skills(skills_match.group(1))
    return payload


def parse_mixed_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = re.search(r"Candidate:\s*([^\n]+)", text).group(1).strip()
    payload["education"] = [
        {"degree": degree.strip(), "school": school.strip(), "year": year.strip()}
        for degree, school, year in re.findall(r"\| ([^|]+) \| ([^|]+) \| (\d{4}) \|", text)
        if "Degree" not in degree
    ]
    # BUG: only the later company is kept from the narrative block.
    later_match = re.search(r"joined ([A-Za-z ]+) in (\d{4}) as a ([^\.]+)", text, re.I)
    if later_match:
        payload["work_experience"].append(
            {
                "company": later_match.group(1).strip(),
                "title": later_match.group(3).strip(),
                "years": f"{later_match.group(2)}-present",
            }
        )
    payload["skills"] = _split_skills(text.split("## Skills", 1)[1])
    return payload


def parse_outline_resume(source: Path, text: str) -> dict:
    payload = _base_payload(source, text)
    payload["name"] = re.search(r"1\.1 Name:\s*([^\n]+)", text).group(1).strip()
    payload["education"] = [
        {"degree": degree.strip(), "school": school.strip(), "year": year.strip()}
        for degree, school, year in re.findall(r"2\.\d ([^|]+) \| ([^|]+) \| (\d{4})", text)
    ]
    payload["work_experience"] = [
        {"company": company.strip(), "title": title.strip(), "years": years.strip()}
        for company, title, years in re.findall(r"3\.\d ([^|]+) \| ([^|]+) \| (\d{4}-\d{4})", text)
    ]
    payload["skills"] = [skill.strip() for skill in re.findall(r"4\.\d ([^\n]+)", text)]
    return payload
