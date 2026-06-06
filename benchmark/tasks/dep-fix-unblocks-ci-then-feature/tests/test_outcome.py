"""Outcome verifier for E1-LS2-T4: dep-fix-unblocks-ci-then-feature."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parents[1]
COPIED_TASK_ROOT = TASK_DIR / "project"
PROJECT = COPIED_TASK_ROOT / "project"
LOCAL_INDEX = COPIED_TASK_ROOT / "local_index"


def _install():
    tmp = tempfile.TemporaryDirectory()
    site = Path(tmp.name) / "site"
    site.mkdir()
    env = os.environ.copy()
    env["PIP_NO_INDEX"] = "1"
    env["PIP_FIND_LINKS"] = str(LOCAL_INDEX)
    r = subprocess.run(
        ["python3", "-m", "pip", "install", "--target", str(site),
         "-r", str(PROJECT / "requirements.txt")],
        cwd=str(PROJECT),
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    return tmp, site, r


def _py(site, code):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site) + os.pathsep + str(PROJECT / "src")
    return subprocess.run(
        ["python3", "-c", code], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
    )


# ── Public ────────────────────────────────────────────────────────────────

def test_public_install_succeeds():
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, f"pip install failed:\n{r.stderr}"
    finally:
        tmp.cleanup()


def test_public_import_succeeds():
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, "from analytics import compute_statistics; print('ok')")
        assert t.returncode == 0, f"Import failed:\n{t.stderr}"
    finally:
        tmp.cleanup()


# ── Hidden ────────────────────────────────────────────────────────────────

@pytest.mark.hidden
def test_hidden_h1_csv_endpoint():
    """GET /api/reports/export.csv returns CSV with correct columns."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from app import app
c = app.test_client()
r = c.get("/api/reports/export.csv")
assert r.status_code == 200, f"status={r.status_code}"
assert r.content_type == "text/csv", f"type={r.content_type}"
lines = [l.strip() for l in r.data.strip().splitlines()]
assert lines[0] == "date,metric,region,value", f"header: {lines[0]!r}"
assert len(lines) >= 2
print(f"ok: {len(lines)} lines")
""")
        assert t.returncode == 0, f"CSV endpoint:\n{t.stderr}\n{t.stdout}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h2_date_filter():
    """Endpoint filters records by start_date/end_date query params."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from app import app
c = app.test_client()
r = c.get("/api/reports/export.csv", query_string={"start_date": "2024-02-01", "end_date": "2024-02-28"})
assert r.status_code == 200
lines = [l.strip() for l in r.data.strip().splitlines()]
for line in lines[1:]:
    assert line.startswith("2024-02-"), f"unexpected: {line!r}"
assert "2024-01-" not in r.data
assert "2024-03-" not in r.data
print(f"ok: {len(lines)-1} rows")
""")
        assert t.returncode == 0, f"Date filter:\n{t.stderr}\n{t.stdout}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h2b_csv_filter_edge_cases():
    """CSV export handles one-sided filters and no-match results."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from app import app
c = app.test_client()

start_only = c.get('/api/reports/export.csv', query_string={'start_date': '2024-02-01'})
assert start_only.status_code == 200
text = start_only.data.decode()
assert '2024-01-' not in text
assert '2024-02-' in text and '2024-03-' in text

end_only = c.get('/api/reports/export.csv', query_string={'end_date': '2024-01-31'})
assert end_only.status_code == 200
text = end_only.data.decode()
assert '2024-01-' in text
assert '2024-02-' not in text and '2024-03-' not in text

none = c.get('/api/reports/export.csv', query_string={'start_date': '2099-01-01'})
assert none.status_code == 200
assert none.data.decode() == 'date,metric,region,value'
print('ok')
""")
        assert t.returncode == 0, f"CSV filter edge cases:\n{t.stderr}\n{t.stdout}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h2c_export_empty_records_contract():
    """The export helper handles empty inputs as documented."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from analytics.export import export_to_csv
assert export_to_csv([], columns=['date', 'metric']) == 'date,metric'
assert export_to_csv([], columns=None) == ''
print('ok')
""")
        assert t.returncode == 0, f"CSV empty-record contract:\n{t.stderr}\n{t.stdout}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h3_scipy_not_regressed():
    """scipy-based analytics still work after dependency changes."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from analytics.stats import compute_statistics, compute_correlation
r = compute_statistics([10, 20, 30, 40, 50])
assert r["count"] == 5
c = compute_correlation([1,2,3,4,5], [2,4,6,8,10])
assert abs(c - 1.0) < 0.01
print("ok")
""")
        assert t.returncode == 0, f"scipy regression:\n{t.stderr}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h4_numpy_satisfies_all():
    """Installed numpy version satisfies scipy (>=1.26) and all other packages."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
import numpy, scipy, custom_ml_utils
v = tuple(int(x) for x in numpy.__version__.split("."))
assert v >= (1, 26), f"numpy {numpy.__version__} < 1.26 — scipy needs >=1.26"
# Verify custom_ml_utils works with this numpy
from custom_ml_utils import normalize
assert normalize([10, 20, 30]) == [0.0, 0.5, 1.0]
print(f"numpy={numpy.__version__} ml_utils={custom_ml_utils.__version__}")
""")
        assert t.returncode == 0, f"numpy check:\n{t.stderr}"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h5_clean_env_and_summary():
    """No unresolved dependency conflicts AND existing endpoint still works."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        # Real dependency consistency check: read each package's METADATA,
        # extract Requires-Dist, verify constraints are satisfied.
        t = _py(site, """
import json, os, re, sys
from pathlib import Path

# Find site dir (the one with dist-info directories)
site = None
for p in sys.path:
    pp = Path(p)
    if pp.is_dir() and list(pp.glob("*.dist-info")):
        site = pp; break
assert site, "No dist-info found in PYTHONPATH"

# Collect installed package versions
installed = {}
for di in site.glob("*.dist-info"):
    meta = (di / "METADATA").read_text()
    name = re.search(r"^Name: (.+)$", meta, re.M).group(1).strip().lower().replace("-", "_")
    ver = re.search(r"^Version: (.+)$", meta, re.M).group(1).strip()
    installed[name] = ver

# Check each package's requirements against installed versions
from packaging.specifiers import SpecifierSet
from packaging.version import Version

errors = []
for di in site.glob("*.dist-info"):
    meta = (di / "METADATA").read_text()
    pkg_name = re.search(r"^Name: (.+)$", meta, re.M).group(1).strip()
    for m in re.finditer(r"^Requires-Dist: (.+)$", meta, re.M):
        req_str = m.group(1).strip()
        # Parse: "numpy>=1.26" or "numpy<1.25"
        rm = re.match(r"([a-zA-Z0-9_-]+)\\s*(.*)", req_str)
        if not rm:
            continue
        dep_name = rm.group(1).lower().replace("-", "_")
        spec_str = rm.group(2).strip()
        if dep_name not in installed:
            errors.append(f"{pkg_name} requires {dep_name} but it's not installed")
            continue
        if spec_str:
            spec = SpecifierSet(spec_str)
            ver = Version(installed[dep_name])
            if ver not in spec:
                errors.append(f"{pkg_name} requires {dep_name}{spec_str} but {installed[dep_name]} is installed")

if errors:
    print("CONFLICTS:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"clean: {len(installed)} packages, 0 conflicts")

# Also verify existing endpoint works
from app import app
c = app.test_client()
r = c.get("/api/reports/summary")
assert r.status_code == 200
data = json.loads(r.data)
assert data["record_count"] > 0
print(f"summary ok: {data['record_count']} records")
""")
        assert t.returncode == 0, (
            f"Environment has dependency conflicts or summary broken:\n{t.stderr}\n{t.stdout}"
        )
    finally:
        tmp.cleanup()
