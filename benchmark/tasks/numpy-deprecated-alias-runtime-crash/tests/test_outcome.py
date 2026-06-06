"""Outcome verifier for E1-LS2-T5: numpy-deprecated-alias-runtime-crash.

Trap matrix:
- Pin numpy<1.24  → public tests mostly pass, H4 fails (mini_sklearn needs >=1.24)
- Fix only first np.float → public scalar test passes, H1/H2/H3 fail on remaining aliases
- Fix all aliases + keep numpy modern → all pass
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parents[1]
ML = TASK_DIR / "project" / "ml_pipeline"
LOCAL_INDEX = TASK_DIR / "project" / "local_index"


def _install():
    tmp = tempfile.TemporaryDirectory()
    site = Path(tmp.name) / "site"
    site.mkdir()
    env = os.environ.copy()
    env["PIP_NO_INDEX"] = "1"
    env["PIP_FIND_LINKS"] = str(LOCAL_INDEX)
    r = subprocess.run(
        ["python3", "-m", "pip", "install", "--target", str(site),
         "-r", str(ML / "requirements.txt")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    return tmp, site, r


def _py(site, code):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site) + os.pathsep + str(ML / "src")
    return subprocess.run(
        ["python3", "-c", code], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
    )


# ── Public tests (designed so pin-old-numpy partially passes) ─────────────

def test_public_basic_load_data():
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from data_pipeline import load_data
r = load_data([{"a": "1.5", "b": "hello"}])
assert r[0]["a"] == 1.5 and r[0]["b"] == "hello"
print("ok")
""")
        assert t.returncode == 0, f"load_data failed:\n{t.stderr}"
    finally:
        tmp.cleanup()


def test_public_basic_calculate_scalar():
    """Hits the first np.float — the one shown in error_log.txt."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from custom_ml_utils import advanced_calculate
r = advanced_calculate(1.5)
assert r == 4.0, f"got {r}"
print("ok")
""")
        assert t.returncode == 0, f"scalar calc failed:\n{t.stderr}"
    finally:
        tmp.cleanup()


def test_public_basic_pipeline_smoke():
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from main import run_basic_pipeline
r = run_basic_pipeline()
assert r["checks"]["status"] == "ok"
assert r["checks"]["count"] == 5
assert isinstance(r["scalar_demo"], (int, float))
assert r["feature_shape"] == [5, 2]
print("ok")
""")
        assert t.returncode == 0, f"pipeline smoke failed:\n{t.stderr}"
    finally:
        tmp.cleanup()


# ── Hidden tests ──────────────────────────────────────────────────────────

@pytest.mark.hidden
def test_hidden_h1_array_path_hits_int_and_bool():
    """advanced_calculate with array hits np.int; prepare_batch hits np.bool."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from custom_ml_utils import advanced_calculate, prepare_batch

# Array path exercises np.float + np.int
r = advanced_calculate([1.0, 2.0, 3.0])
assert isinstance(r, list) and len(r) == 3
assert all(isinstance(v, float) for v in r)

# prepare_batch exercises np.bool
batch = prepare_batch([{"a": 1, "b": 2}, {"c": 3}], keep_metadata=False)
assert isinstance(batch, list) and len(batch) > 0
print("ok")
""")
        assert t.returncode == 0, (
            f"Array/batch path failed — likely np.int or np.bool not fixed:\n{t.stderr}"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h2_complex_features():
    """build_feature_matrix with allow_complex=True hits np.complex."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from feature_engineering import build_feature_matrix
r = build_feature_matrix([10, 20, 30], allow_complex=True)
assert len(r) == 3
assert len(r[0]) == 2  # z-score + magnitude
assert all(isinstance(row[1], float) for row in r)
print("ok")
""")
        assert t.returncode == 0, (
            f"Complex features failed — likely np.complex not fixed:\n{t.stderr}"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h3_object_dtype_detection():
    """detect_dtype with strings hits np.object; prepare_batch with keep_metadata."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
from data_pipeline import detect_dtype
from custom_ml_utils import prepare_batch

assert detect_dtype(["hello", "world"]) == "object"
assert detect_dtype([1, 2, 3]) == "numeric"

batch = prepare_batch(
    [{"x": "1.0", "label": "pos"}, {"x": "2.0", "label": "neg"}],
    keep_metadata=True
)
assert any("label" in rec for rec in batch)
print("ok")
""")
        assert t.returncode == 0, (
            f"Object dtype path failed — likely np.object not fixed:\n{t.stderr}"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h4_sklearn_and_modern_numpy():
    """mini_sklearn works AND numpy>=1.24. Catches pin-old-numpy trap."""
    tmp, site, r = _install()
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, """
import numpy as np
v = tuple(int(x) for x in np.__version__.split("."))
assert v >= (1, 24), f"numpy {np.__version__} too old — mini_sklearn needs >=1.24"

from modeling import fit_model, evaluate_model
model, scaler = fit_model([1,2,3,4,5], [2,4,6,8,10])
result = evaluate_model(model, scaler, [6, 7], [12, 14])
assert result["mean_error"] < 1.0
assert len(result["predictions"]) == 2
print(f"ok numpy={np.__version__}")
""")
        assert t.returncode == 0, (
            f"mini_sklearn/numpy version check failed — "
            f"agent likely pinned numpy<1.24:\n{t.stderr}"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h5_no_alias_residue_in_source():
    """Source contains no deprecated NumPy alias residue.

    Catches the 'fix only traceback's first alias' trap: agent replaces
    np.float but leaves np.int/np.bool/np.object/np.complex untouched.
    """
    SRC = ML / "src"
    # Match both 'numpy.float' and 'np.float' patterns
    deprecated = [
        r"\bnp\.float\b", r"\bnp\.int\b", r"\bnp\.bool\b",
        r"\bnp\.object\b", r"\bnp\.complex\b",
        r"\bnumpy\.float\b", r"\bnumpy\.int\b", r"\bnumpy\.bool\b",
        r"\bnumpy\.object\b", r"\bnumpy\.complex\b",
    ]
    # Exclude legitimate patterns: np.float64, np.int64, np.bool_, np.object_, np.complex128
    legitimate = {"np.float64", "np.int64", "np.bool_", "np.object_", "np.complex128",
                  "numpy.float64", "numpy.int64", "numpy.bool_", "numpy.object_", "numpy.complex128"}

    violations = []
    for py_file in SRC.rglob("*.py"):
        code = py_file.read_text()
        for i, line in enumerate(code.splitlines(), 1):
            stripped = line.split("#")[0]  # ignore comments
            for pattern in deprecated:
                if re.search(pattern, stripped):
                    # Check it's not a legitimate modern alias
                    match_text = re.search(pattern, stripped).group()
                    # Look ahead for digits or underscore (float64, bool_, etc.)
                    pos = stripped.find(match_text) + len(match_text)
                    if pos < len(stripped) and (stripped[pos].isdigit() or stripped[pos] == '_'):
                        continue
                    violations.append(f"{py_file.name}:{i}: {match_text}")

    assert not violations, (
        f"Found {len(violations)} deprecated numpy alias(es) in source:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
