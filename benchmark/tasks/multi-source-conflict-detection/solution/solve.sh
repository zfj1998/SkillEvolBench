#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))

policy = root / "conflict_policy.py"
text = policy.read_text(encoding="utf-8")
text = text.replace('SUPPRESS_CONFLICT_FIELDS = {"title"}', 'SUPPRESS_CONFLICT_FIELDS = set()')
policy.write_text(text, encoding="utf-8")

linkage = root / "field_linkage.py"
text = linkage.read_text(encoding="utf-8")
old = '''def expanded_suppression(explicit_fields: set[str]) -> set[str]:
    suppressed = set(explicit_fields)
    for group in LINKED_METADATA_GROUPS:
        if suppressed & group:
            suppressed |= group
    return suppressed
'''
new = '''def expanded_suppression(explicit_fields: set[str]) -> set[str]:
    return set(explicit_fields)
'''
linkage.write_text(text.replace(old, new), encoding="utf-8")
PY

python3 "$PROJECT_ROOT/build_employee_profile.py"
