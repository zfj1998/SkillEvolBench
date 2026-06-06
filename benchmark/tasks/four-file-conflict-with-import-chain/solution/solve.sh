#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path
import re


def feature_side(text):
    return re.sub(
        r"<<<<<<< HEAD\n.*?=======\n(.*?)>>>>>>> feature/add-mode-param",
        lambda m: m.group(1),
        text,
        flags=re.S,
    )


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


utils = feature_side(Path("utils.py").read_text(encoding="utf-8"))
utils = utils.replace("def helper_func(", "def process_data(")
write("utils.py", utils)

for path in ["routes.py", "services.py", "public_tests/test_utils.py"]:
    text = feature_side(Path(path).read_text(encoding="utf-8"))
    text = text.replace("helper_func", "process_data")
    write(path, text)
PY
