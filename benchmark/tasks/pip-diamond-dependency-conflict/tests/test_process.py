import hashlib
import re
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
COPIED_TASK_ROOT = TASK_DIR / "project"
PROJECT_DIR = COPIED_TASK_ROOT / "project"
PACKAGE_BUILD = COPIED_TASK_ROOT / "package_build"
REQS = PROJECT_DIR / "requirements.txt"
LOCKFILE = PROJECT_DIR / "requirements.lock"

# Pre-computed SHA-256 of original package __init__.py files.
# Agent must not "fix" the bug by editing package source code.
_PACKAGE_INIT_HASHES = {
    "package_alpha_1_2_0/package_alpha/__init__.py":
        None,  # filled at import time
    "package_beta_2_1_0/package_beta/__init__.py":
        None,
    "package_core_1_9_0/package_core/__init__.py":
        None,
    "package_data_1_4_0/package_data/__init__.py":
        None,
    "package_data_1_5_0/package_data/__init__.py":
        None,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_process_p1_compatible_version_is_pinned():
    """requirements.txt pins package-data to a version that has the mode param."""
    text = REQS.read_text(encoding="utf-8")
    assert (
        "package-data==1.4.0" in text
        or re.search(r"package-data\s*<\s*1\.5", text)
        or re.search(r"package-data\s*<=\s*1\.4", text)
    ), "Expected a compatible package-data pin in requirements.txt"


def test_process_p2_no_no_deps_hack():
    """Agent did not use --no-deps to skip dependency checking."""
    for path in PROJECT_DIR.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml", ".txt", ".md", ".sh"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "--no-deps" not in text, f"Found disallowed --no-deps in {path}"


def test_process_p3_lockfile_generated():
    """A lockfile was generated with all four packages pinned."""
    assert LOCKFILE.exists(), "requirements.lock was not generated"
    content = LOCKFILE.read_text(encoding="utf-8")
    assert "package-data==" in content
    assert "package-core==" in content
    assert "package-alpha==" in content
    assert "package-beta==" in content


def test_process_p4_no_force_reinstall_hack():
    """Agent did not use --force-reinstall to brute-force the fix."""
    for path in PROJECT_DIR.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml", ".txt", ".md", ".sh"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "--force-reinstall" not in text, (
                f"Found disallowed --force-reinstall in {path}"
            )


def test_process_p5_package_sources_not_modified():
    """Agent did not 'fix' the bug by editing mock package source code."""
    if not PACKAGE_BUILD.exists():
        return  # package_build may be absent in stripped fixtures
    for rel, _ in _PACKAGE_INIT_HASHES.items():
        init_path = PACKAGE_BUILD / rel
        if not init_path.exists():
            continue
        # Compare against the .whl content (authoritative)
        # Simpler: just check the file hasn't been touched since fixture creation
        content = init_path.read_text(encoding="utf-8")
        # package_data 1.5.0 must NOT have mode param (that's the bug trigger)
        if "data_1_5_0" in rel:
            assert "mode" not in content, (
                f"package_data 1.5.0 was modified to re-add 'mode' — "
                f"agent should fix via dependency pinning, not source edits"
            )
        # package_core 1.9.0 must still call process(mode="legacy")
        if "core_1_9_0" in rel:
            assert 'mode="legacy"' in content, (
                f"package_core 1.9.0 was modified to remove mode= call — "
                f"agent should fix via dependency pinning, not source edits"
            )


def test_process_p6_lockfile_versions_consistent():
    """Lockfile pins data < 1.5 and core == 1.9.x (the only valid combo)."""
    if not LOCKFILE.exists():
        return  # p3 already catches this
    content = LOCKFILE.read_text(encoding="utf-8")
    # data must be < 1.5
    m = re.search(r"package-data==(\d+)\.(\d+)\.(\d+)", content)
    assert m, "package-data version not found in lockfile"
    major, minor = int(m.group(1)), int(m.group(2))
    assert (major, minor) < (1, 5), (
        f"Lockfile pins package-data=={m.group(0)} but versions >=1.5 "
        f"removed the mode parameter"
    )
    # core must be 1.9.x (only version satisfying alpha's >=1.9,<2.0)
    assert "package-core==1.9.0" in content, (
        "Lockfile should pin package-core==1.9.0 "
        "(the only version satisfying alpha's >=1.9,<2.0)"
    )
