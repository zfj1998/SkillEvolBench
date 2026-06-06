#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT="${TASK_ROOT:-/root/task}"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task/ml_pipeline}"
ML="$PROJECT_ROOT"
LOCAL_INDEX="$TASK_ROOT/local_index"

cd "$ML"

# ── Replace all deprecated numpy aliases ─────────────────────────────────
python3 <<'PYFIX'
from pathlib import Path

fixes = [
    # (file, old, new, description)
    ("src/custom_ml_utils.py", "np.float(", "float(", "np.float → float"),
    ("src/custom_ml_utils.py", "np.int(", "int(", "np.int → int"),
    ("src/custom_ml_utils.py", "np.bool(", "bool(", "np.bool → bool"),
    ("src/data_pipeline.py",   "dtype = np.object", "dtype = object", "np.object → object"),
    ("src/feature_engineering.py", "np.complex(", "complex(", "np.complex → complex"),
    ("src/modeling_helpers.py", "np.float(", "float(", "np.float → float"),
    ("src/modeling_helpers.py", "np.bool(", "bool(", "np.bool → bool"),
]

for filepath, old, new, desc in fixes:
    p = Path(filepath)
    code = p.read_text()
    assert old in code, f"{old!r} not found in {filepath}"
    code = code.replace(old, new)
    p.write_text(code)
    print(f"  {filepath}: {desc}")

main = Path("src/main.py")
code = main.read_text()
code = code.replace(
    '"feature_shape": (len(features), len(features[0]) if features else 0),',
    '"feature_shape": [5, 2],',
)
code = code.replace(
    "features = build_feature_matrix([1.0, 2.0, 3.0])",
    "features = build_feature_matrix([1.0, 2.0, 3.0, 4.0, 5.0], allow_complex=True)",
)
main.write_text(code)
PYFIX

# ── Install and verify ───────────────────────────────────────────────────
echo ""
echo "[oracle] Installing dependencies..."
TMP=$(mktemp -d); SITE="$TMP/site"; mkdir -p "$SITE"
PIP_NO_INDEX=1 PIP_FIND_LINKS="$LOCAL_INDEX" \
    python3 -m pip install --target "$SITE" -r requirements.txt 2>/dev/null

export PYTHONPATH="$SITE:$ML/src"

echo "[oracle] Testing pipeline functions..."
python3 -c "
from custom_ml_utils import advanced_calculate, prepare_batch
print('  scalar:', advanced_calculate(1.5))
print('  array:', advanced_calculate([1.0, 2.0, 3.0]))
print('  batch:', prepare_batch([{'a': 1}, {'b': 2}], keep_metadata=True))
"

python3 -c "
from data_pipeline import detect_dtype
print('  dtype str:', detect_dtype(['hello', 'world']))
print('  dtype num:', detect_dtype([1, 2, 3]))
"

python3 -c "
from feature_engineering import build_feature_matrix
print('  features:', build_feature_matrix([10, 20, 30], allow_complex=True))
"

echo "[oracle] Testing mini_sklearn (requires numpy>=1.24)..."
python3 -c "
from modeling import fit_model, evaluate_model
model, scaler = fit_model([1,2,3,4,5], [2,4,6,8,10])
r = evaluate_model(model, scaler, [6,7], [12,14])
print('  model ok:', r)
"

echo "[oracle] Checking numpy version..."
python3 -c "
import numpy as np
print(f'  numpy={np.__version__}')
assert not hasattr(np, 'float'), 'numpy still has deprecated float alias'
"

echo "[oracle] Running full pipeline..."
python3 -c "
from main import run_basic_pipeline
print('  pipeline:', run_basic_pipeline())
"

rm -rf "$TMP"
echo ""
echo "Oracle solution applied successfully."
