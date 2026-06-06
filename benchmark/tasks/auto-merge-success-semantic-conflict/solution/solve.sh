#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from pathlib import Path

validators = Path("validators.py").read_text(encoding="utf-8")
first = validators.find("def validate_input")
second = validators.find("def validate_input", first + 1)
validators = (
    validators[:first]
    + validators[first:second].replace("def validate_input", "def validate_email", 1)
    + validators[second:].replace("def validate_input", "def validate_phone", 1)
)
Path("validators.py").write_text(validators, encoding="utf-8")

app = Path("app.py").read_text(encoding="utf-8")
app = app.replace(
    "from validators import validate_input, validate_name, validate_age",
    "from validators import validate_email, validate_phone, validate_name, validate_age",
)
app = app.replace("email_result = validate_input(email)", "email_result = validate_email(email)")
app = app.replace("phone_result = validate_input(phone)", "phone_result = validate_phone(phone)")
Path("app.py").write_text(app, encoding="utf-8")
PY
