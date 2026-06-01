#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task/project}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
LOCAL_INDEX="$TASK_ROOT/local_index"

# ── Step 1: Pin package-data==1.4.0 in requirements.txt ─────────────────
PROJECT_ROOT="$PROJECT_ROOT" python3 <<'PY1'
import os
from pathlib import Path
project = Path(os.environ["PROJECT_ROOT"])
req = project / "requirements.txt"
text = req.read_text(encoding="utf-8")
if "package-data==1.4.0" not in text:
    text = text.rstrip() + "\npackage-data==1.4.0\n"
    req.write_text(text, encoding="utf-8")
PY1

# ── Step 2: Install into temp site-dir and verify runtime ────────────────
rm -f "$PROJECT_ROOT/requirements.lock"
TMP_DIR=$(mktemp -d)
SITE_DIR="$TMP_DIR/site"
mkdir -p "$SITE_DIR"

PIP_NO_INDEX=1 PIP_FIND_LINKS="$LOCAL_INDEX" \
    python3 -m pip install --target "$SITE_DIR" \
    -r "$PROJECT_ROOT/requirements.txt" >/dev/null

PYTHONPATH="$SITE_DIR:$PROJECT_ROOT" python3 - <<'PY2'
from src.main import run_alpha_feature, run_beta_feature, run_combined
assert run_alpha_feature() == "alpha:legacy:sample"
assert run_beta_feature() == "beta:SAMPLE"
assert run_combined() == "alpha:legacy:sample | beta:SAMPLE"
PY2

# ── Step 3: Generate lockfile ────────────────────────────────────────────
SITE_DIR="$SITE_DIR" PROJECT_ROOT="$PROJECT_ROOT" python3 - <<'PY3'
import os, sys
from pathlib import Path
from importlib.metadata import version
site_dir = os.environ["SITE_DIR"]
sys.path.insert(0, site_dir)
out = Path(os.environ["PROJECT_ROOT"]) / "requirements.lock"
lines = [
    f"package-alpha=={version('package-alpha')}",
    f"package-beta=={version('package-beta')}",
    f"package-core=={version('package-core')}",
    f"package-data=={version('package-data')}",
]
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY3

rm -rf "$TMP_DIR"
echo "Oracle solution applied successfully."
