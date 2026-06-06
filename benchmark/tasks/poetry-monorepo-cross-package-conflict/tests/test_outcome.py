import json
import shutil
import subprocess
from pathlib import Path

import pytest

TASK_ROOT = Path(__file__).resolve().parents[1]
MONOREPO = TASK_ROOT / "project" / "monorepo"


def clean_env():
    env_dir = MONOREPO / ".poetry_env"
    if env_dir.exists():
        shutil.rmtree(env_dir)
    lock_path = MONOREPO / "poetry.lock"
    if lock_path.exists():
        lock_path.unlink()


def run_poetry(*args):
    return subprocess.run(
        [str(MONOREPO / "poetry"), *args],
        cwd=MONOREPO,
        capture_output=True,
        text=True,
    )


def run_python(code: str):
    return subprocess.run(
        [str(MONOREPO / "poetry"), "run", "python", "-c", code],
        cwd=MONOREPO,
        capture_output=True,
        text=True,
    )


def test_public_install_succeeds():
    clean_env()
    result = run_poetry("install")
    assert result.returncode == 0, result.stderr + result.stdout
    assert (MONOREPO / "poetry.lock").exists()


def test_public_worker_imports_core_and_api():
    clean_env()
    assert run_poetry("install").returncode == 0
    result = run_python("from worker_pkg import run_worker; import core_pkg, api_pkg; print(run_worker())")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "WORKER" in result.stdout


@pytest.mark.hidden
def test_hidden_core_uses_pydantic_v2_features():
    clean_env()
    assert run_poetry("install").returncode == 0
    code = """
from core_pkg import build_core_record
record = build_core_record("core", 5)
print(record.model_dump())
"""
    result = run_python(code)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "'name': 'CORE'" in result.stdout


@pytest.mark.hidden
def test_hidden_api_endpoint_logic_works():
    clean_env()
    assert run_poetry("install").returncode == 0
    code = """
from api_pkg import create_job
print(create_job('  nightly ingest  ', 7))
"""
    result = run_python(code)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Nightly Ingest" in result.stdout


@pytest.mark.hidden
def test_hidden_worker_integration():
    clean_env()
    assert run_poetry("install").returncode == 0
    code = """
from worker_pkg import run_worker
print(run_worker())
"""
    result = run_python(code)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "WORKER::Worker Queue" in result.stdout


@pytest.mark.hidden
def test_hidden_single_pydantic_version_in_lock():
    clean_env()
    assert run_poetry("install").returncode == 0
    lock = json.loads((MONOREPO / "poetry.lock").read_text())
    pydantic_versions = [pkg["version"] for pkg in lock["package"] if pkg["name"] == "pydantic"]
    assert pydantic_versions == ["2.5.0"], lock
