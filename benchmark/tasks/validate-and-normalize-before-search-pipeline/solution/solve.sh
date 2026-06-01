#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
path = root / "pipeline.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    '    validate_params(internal_request)\n'
    '    api_payload = build_api_payload(internal_request)\n',
    '    errors = validate_params(internal_request)\n'
    '    if errors:\n'
    '        raise ValueError(errors)\n'
    '    api_payload = build_api_payload(internal_request)\n',
)
path.write_text(text, encoding="utf-8")

assembly = root / "request_assembly.py"
assembly.write_text(
    '''from __future__ import annotations


def build_internal_request(params):
    internal = dict(params)
    if internal.get("region") == "California":
        internal["state_code"] = "CA"
    if internal.get("sort_phrase") == "amount descending":
        internal["sort_by"] = "amount"
        internal["sort_direction"] = "desc"
    return internal


def build_api_payload(internal_request):
    return {
        "region_code": internal_request["state_code"],
        "start_date": internal_request["start_date"],
        "end_date": internal_request["end_date"],
        "sort_by": internal_request["sort_by"],
        "sort_order": internal_request["sort_direction"],
    }
''',
    encoding="utf-8",
)
PY
