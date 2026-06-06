#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path
import re

path = Path("config.yaml")
text = path.read_text(encoding="utf-8")

def merge_conflict(match):
    ours = match.group("ours").splitlines()
    theirs = match.group("theirs").splitlines()
    pool_size = next(line for line in ours if line.strip().startswith("pool_size:"))
    ssl_start = next(i for i, line in enumerate(theirs) if line.strip().startswith("ssl:"))
    ssl_block = theirs[ssl_start:]
    return "\n".join([pool_size, *ssl_block]) + "\n"

text = re.sub(
    r"<<<<<<< HEAD\n(?P<ours>.*?)=======\n(?P<theirs>.*?)>>>>>>> feature/add-ssl\n",
    merge_conflict,
    text,
    flags=re.S,
)
path.write_text(text, encoding="utf-8")
PY
