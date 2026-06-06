import json
import re
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
MONOREPO = TASK_ROOT / "project" / "monorepo"


def read(path: str) -> str:
    return (MONOREPO / path).read_text()


def test_p1_fastapi_upgraded_to_supported_range():
    text = read("packages/api/pyproject.toml")
    assert 'fastapi = "==0.95.0"' not in text
    match = re.search(r'fastapi\s*=\s*"([^"]+)"', text)
    assert match, text
    spec = match.group(1)
    assert "0.100" in spec or "0.101" in spec, spec


def test_p2_pydantic_v2_api_adapted():
    app_text = read("packages/api/api_pkg/app.py")
    assert "field_validator" in app_text
    assert "model_dump(" in app_text
    assert "@validator" not in app_text
    assert ".dict(" not in app_text


def test_p3_workspace_versions_consistent_and_no_split_pydantic_pins():
    versions = []
    for rel in [
        "packages/core/pyproject.toml",
        "packages/api/pyproject.toml",
        "packages/worker/pyproject.toml",
    ]:
        text = read(rel)
        m = re.search(r'version\s*=\s*"([^"]+)"', text)
        assert m, rel
        versions.append(m.group(1))
    assert len(set(versions)) == 1, versions

    api_text = read("packages/api/pyproject.toml")
    worker_text = read("packages/worker/pyproject.toml")
    assert 'pydantic = "<2.0' not in api_text
    assert "pydantic" not in worker_text


def test_p4_no_dependency_bypass_or_lock_hacks():
    for path in MONOREPO.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".py", ".toml", ".md", ".txt", ".sh"} or path.name == "poetry":
            text = path.read_text(errors="ignore").lower()
            assert "--no-deps" not in text, f"forbidden flag in {path}"
    lock_path = MONOREPO / "poetry.lock"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        pyd = [pkg for pkg in lock["package"] if pkg["name"] == "pydantic"]
        assert len(pyd) == 1
        assert pyd[0]["version"].startswith("2.")
