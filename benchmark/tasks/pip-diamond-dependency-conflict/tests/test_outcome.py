import os
import subprocess
import tempfile
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parents[1]
COPIED_TASK_ROOT = TASK_DIR / "project"
PROJECT_DIR = COPIED_TASK_ROOT / "project"
LOCAL_INDEX = COPIED_TASK_ROOT / "local_index"
LOCKFILE = PROJECT_DIR / "requirements.lock"


def _install_project():
    tmp = tempfile.TemporaryDirectory()
    site_dir = Path(tmp.name) / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PIP_NO_INDEX"] = "1"
    env["PIP_FIND_LINKS"] = str(LOCAL_INDEX)
    result = subprocess.run(
        ["python3", "-m", "pip", "install", "--target", str(site_dir),
         "-r", str(PROJECT_DIR / "requirements.txt")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return tmp, site_dir, result


def _run_python(site_dir, code):
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(site_dir) + os.pathsep +
        str(PROJECT_DIR) + os.pathsep +
        env.get("PYTHONPATH", "")
    )
    return subprocess.run(
        ["python3", "-c", code],
        env=env, cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


# ── Public tests ──────────────────────────────────────────────────────────

def test_public_requirements_install_succeeds():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
    finally:
        tmp.cleanup()


def test_public_import_main_succeeds():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        run = _run_python(site_dir,
            "from src.main import run_alpha_feature, run_beta_feature, run_combined; print('ok')")
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "ok"
    finally:
        tmp.cleanup()


def test_public_runtime_smoke_checks_pass():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        code = (
            "from src.main import run_alpha_feature, run_beta_feature, run_combined; "
            "assert run_alpha_feature() == 'alpha:legacy:sample'; "
            "assert run_beta_feature() == 'beta:SAMPLE'; "
            "assert run_combined() == 'alpha:legacy:sample | beta:SAMPLE'; "
            "print('ok')"
        )
        run = _run_python(site_dir, code)
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "ok"
    finally:
        tmp.cleanup()


# ── Hidden tests ──────────────────────────────────────────────────────────

@pytest.mark.hidden
def test_hidden_alpha_feature_succeeds():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        run = _run_python(site_dir,
            "from src.main import run_alpha_feature; print(run_alpha_feature())")
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "alpha:legacy:sample"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_beta_feature_succeeds():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        run = _run_python(site_dir,
            "from src.main import run_beta_feature; print(run_beta_feature())")
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "beta:SAMPLE"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_combined_feature_succeeds():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        run = _run_python(site_dir,
            "from src.main import run_combined; print(run_combined())")
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "alpha:legacy:sample | beta:SAMPLE"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_installed_versions_match_expected_combo():
    tmp, site_dir, result = _install_project()
    try:
        assert result.returncode == 0, result.stderr
        code = (
            "import sys; from importlib.metadata import version; "
            f"sys.path.insert(0, r'{site_dir}'); "
            "print(version('package-alpha')); "
            "print(version('package-beta')); "
            "print(version('package-core')); "
            "print(version('package-data'))"
        )
        run = _run_python(site_dir, code)
        assert run.returncode == 0, run.stderr
        lines = run.stdout.strip().splitlines()
        assert lines == ["1.2.0", "2.1.0", "1.9.0", "1.4.0"]
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_lockfile_matches_installed_versions():
    assert LOCKFILE.exists(), "requirements.lock not found"
    content = LOCKFILE.read_text(encoding="utf-8")
    for expected in [
        "package-data==1.4.0",
        "package-core==1.9.0",
        "package-alpha==1.2.0",
        "package-beta==2.1.0",
    ]:
        assert expected in content
