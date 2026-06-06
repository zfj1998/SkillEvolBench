"""Process verifier for E1-LS2-T5.

P1: All 5 deprecated aliases replaced
P2: numpy not pinned to <1.24
P3: Replacements are semantically correct (accepts multiple valid forms)
P4: Modifications span at least 3 source files
"""

import re
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
ML = TASK_DIR / "project" / "ml_pipeline"
SRC = ML / "src"


def _scan_deprecated(code):
    """Return list of deprecated alias uses in code (ignoring comments and modern aliases)."""
    deprecated_patterns = [
        r"\bnp\.float\b", r"\bnp\.int\b", r"\bnp\.bool\b",
        r"\bnp\.object\b", r"\bnp\.complex\b",
        r"\bnumpy\.float\b", r"\bnumpy\.int\b", r"\bnumpy\.bool\b",
        r"\bnumpy\.object\b", r"\bnumpy\.complex\b",
    ]
    hits = []
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.split("#")[0]
        for pattern in deprecated_patterns:
            m = re.search(pattern, stripped)
            if m:
                text = m.group()
                pos = m.end()
                if pos < len(stripped) and (stripped[pos].isdigit() or stripped[pos] == '_'):
                    continue  # np.float64, np.bool_, etc. are fine
                hits.append((i, text))
    return hits


def test_process_p1_all_aliases_replaced():
    """All 5 deprecated alias usages removed from source."""
    total = []
    for py_file in SRC.rglob("*.py"):
        hits = _scan_deprecated(py_file.read_text())
        for line_no, text in hits:
            total.append(f"{py_file.name}:{line_no}: {text}")
    assert not total, (
        f"{len(total)} deprecated alias(es) still present:\n"
        + "\n".join(f"  {t}" for t in total)
    )


def test_process_p2_numpy_not_pinned_old():
    """No file pins numpy to <1.24."""
    for f in ML.rglob("*.txt"):
        if "local_index" in str(f):
            continue
        text = f.read_text()
        if re.search(r"numpy\s*[<!=]+\s*1\.(2[0-3]|1[0-9]|[0-9])\b", text):
            raise AssertionError(f"{f.name} pins numpy to pre-1.24")
    for f in ML.rglob("*.cfg"):
        text = f.read_text()
        if re.search(r"numpy\s*<\s*1\.24", text):
            raise AssertionError(f"{f.name} pins numpy<1.24")


def test_process_p3_correct_replacements():
    """Replacements use semantically correct modern types.

    Accepts multiple valid forms:
    - np.float → float / np.float64
    - np.int   → int / np.int64
    - np.bool  → bool / np.bool_
    - np.object → object / np.object_ / str check
    - np.complex → complex / np.complex128
    """
    cml = (SRC / "custom_ml_utils.py").read_text()
    dp = (SRC / "data_pipeline.py").read_text()
    fe = (SRC / "feature_engineering.py").read_text()

    # custom_ml_utils: float conversion, int conversion, bool conversion
    assert re.search(r"\bfloat\(|np\.float64\(", cml), (
        "np.float not replaced with float() or np.float64() in custom_ml_utils.py"
    )
    assert re.search(r"\bint\(|np\.int64\(", cml), (
        "np.int not replaced with int() or np.int64() in custom_ml_utils.py"
    )
    assert re.search(r"\bbool\(|np\.bool_\(", cml), (
        "np.bool not replaced with bool() or np.bool_() in custom_ml_utils.py"
    )

    # data_pipeline: object dtype label (check non-comment code only)
    dp_code_only = "\n".join(line.split("#")[0] for line in dp.splitlines())
    assert "np.object" not in dp_code_only or "np.object_" in dp_code_only, (
        "np.object still used in data_pipeline.py code"
    )
    assert re.search(r"\bobject\b", dp_code_only), (
        "np.object not replaced with object in data_pipeline.py"
    )

    # feature_engineering: complex construction
    assert re.search(r"\bcomplex\(|np\.complex128\(", fe), (
        "np.complex not replaced with complex() or np.complex128() in feature_engineering.py"
    )


def test_process_p4_changes_span_multiple_files():
    """Changes span at least 3 source files.

    Note: this verifies coverage by checking that each of the 3 files
    containing deprecated aliases has been fully cleaned. This is an
    approximation of 'agent ran full test suite' that does not rely on
    trace-level information.
    """
    # We check that each of the 3 files with aliases no longer has them
    files_clean = 0
    for filename in ["custom_ml_utils.py", "data_pipeline.py", "feature_engineering.py"]:
        code = (SRC / filename).read_text()
        hits = _scan_deprecated(code)
        if not hits:
            files_clean += 1
    assert files_clean >= 3, (
        f"Only {files_clean}/3 files have all deprecated aliases removed. "
        f"Agent may have only fixed the file mentioned in the error log."
    )
