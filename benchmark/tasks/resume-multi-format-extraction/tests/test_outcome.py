import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
RUNNER = PROJECT / "run_analysis.py"
OUTPUT = PROJECT / "output.json"


def run_extraction():
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run([sys.executable, str(RUNNER)], check=True, cwd=str(PROJECT))
    assert OUTPUT.exists(), "output.json was not created"
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def _by_source():
    payload = run_extraction()
    assert "resumes" in payload and len(payload["resumes"]) == 5
    return {item["source"]: item for item in payload["resumes"]}


def test_public_table_and_list_names_correct():
    by_source = _by_source()
    assert by_source["resume_table.md"]["name"] == "Alice Johnson"
    assert by_source["resume_list.txt"]["name"] == "Brian Lee"


def test_public_has_five_resume_objects():
    payload = run_extraction()
    assert len(payload["resumes"]) == 5


def test_hidden_paragraph_work_experience_correct():
    paragraph = _by_source()["resume_paragraph.txt"]
    companies = {item["company"] for item in paragraph["work_experience"]}
    assert {"Google", "Stripe"} <= companies


def test_hidden_paragraph_work_experience_count_exact():
    paragraph = _by_source()["resume_paragraph.txt"]
    assert len(paragraph["work_experience"]) == 2


def test_hidden_paragraph_education_has_two_entries():
    paragraph = _by_source()["resume_paragraph.txt"]
    schools = {item["school"] for item in paragraph["education"]}
    assert {"MIT", "Stanford"} <= schools


def test_hidden_paragraph_education_count_exact():
    paragraph = _by_source()["resume_paragraph.txt"]
    assert len(paragraph["education"]) == 2


def test_hidden_mixed_resume_table_and_narrative_both_captured():
    mixed = _by_source()["resume_mixed.md"]
    assert mixed["education"][0]["school"] == "Anna University"
    companies = {item["company"] for item in mixed["work_experience"]}
    assert {"Atlassian", "Infosys"} <= companies


def test_hidden_mixed_resume_work_history_count_exact():
    mixed = _by_source()["resume_mixed.md"]
    assert len(mixed["work_experience"]) == 2


def test_hidden_all_names_are_correct():
    by_source = _by_source()
    assert {
        by_source["resume_table.md"]["name"],
        by_source["resume_list.txt"]["name"],
        by_source["resume_paragraph.txt"]["name"],
        by_source["resume_mixed.md"]["name"],
        by_source["resume_outline.txt"]["name"],
    } == {"Alice Johnson", "Brian Lee", "John Patel", "Priya Nair", "Elena Gomez"}


def test_hidden_email_shapes_are_valid():
    for item in run_extraction()["resumes"]:
        assert "@" in item["email"]
        assert "." in item["email"].split("@", 1)[1]


def test_hidden_phone_numbers_are_correct():
    by_source = _by_source()
    assert by_source["resume_table.md"]["phone"] == "555-0100"
    assert by_source["resume_list.txt"]["phone"] == "555-0101"
    assert by_source["resume_paragraph.txt"]["phone"] == "555-0102"
    assert by_source["resume_mixed.md"]["phone"] == "555-0103"
    assert by_source["resume_outline.txt"]["phone"] == "555-0104"


def test_hidden_skills_nonempty_and_without_noise():
    for item in run_extraction()["resumes"]:
        assert item["skills"]
        lowered = {skill.lower() for skill in item["skills"]}
        assert "skills" not in lowered
        assert "experience narrative" not in lowered
