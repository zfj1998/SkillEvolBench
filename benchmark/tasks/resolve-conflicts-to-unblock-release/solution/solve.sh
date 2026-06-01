#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path
import json
import re

auth_path = Path("src/auth.py")
auth = auth_path.read_text(encoding="utf-8")
auth = re.sub(
    r"<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> develop",
    lambda m: m.group(1).replace(
        "def authenticate(username, password):",
        "def authenticate(username, password, remember_me=False):",
    ).replace(
        'return {"success": True, "token": _generate_token(user)}',
        'token = _generate_token(user, long_lived=remember_me)\n        return {"success": True, "token": token, "remember_me": remember_me}',
    ),
    auth,
    flags=re.S,
)
auth_path.write_text(auth, encoding="utf-8")

pkg_path = Path("package.json")
raw = pkg_path.read_text(encoding="utf-8")
raw = re.sub(r"<<<<<<< HEAD\n.*?=======\n(.*?)>>>>>>> develop", r"\1", raw, flags=re.S)
pkg = json.loads(raw)
pkg["version"] = "2.1.0"
pkg["dependencies"]["flask"] = "2.3.0"
pkg_path.write_text(json.dumps(pkg, indent=4) + "\n", encoding="utf-8")

changelog_path = Path("CHANGELOG.md")
changelog = changelog_path.read_text(encoding="utf-8")
changelog = re.sub(
    r"<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> develop",
    "## v2.1.0 (2024-04-10)\n- Added: Remember me functionality\n- Added: User notification system\n- Added: Data export feature\n\n\\1",
    changelog,
    flags=re.S,
)
changelog_path.write_text(changelog, encoding="utf-8")
PY
