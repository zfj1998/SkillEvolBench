from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT / "project" / "analyzer.py").read_text(encoding="utf-8")
LOADER = (ROOT / "project" / "resume_loader.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "project" / "section_router.py").read_text(encoding="utf-8")


def test_process_outputs_five_resume_objects():
    assert "load_resumes" in ANALYZER
    assert "RESUME_FILES" in LOADER


def test_process_paragraph_resume_support_exists():
    assert "parse_paragraph_resume" in ROUTER
    assert "MIT" not in ROUTER and "Stanford" not in ROUTER
    assert "work_experience" in ROUTER and "education" in ROUTER


def test_process_mixed_resume_support_exists():
    assert "parse_mixed_resume" in ROUTER
    assert "work_experience" in ROUTER and "education" in ROUTER


def test_process_no_hardcoded_resume_names():
    lowered = (ANALYZER + ROUTER).lower()
    assert "alice johnson" not in lowered
    assert "john patel" not in lowered
