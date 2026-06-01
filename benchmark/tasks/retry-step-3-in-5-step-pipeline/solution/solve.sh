#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
import re
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
source = project / "pipeline_client.py"
text = source.read_text(encoding="utf-8")
text = text.replace("from detail_stage import fetch_details_from_stage\nfrom sync_state import build_sync_context", "from mock_pipeline import TransientServiceError")
text = re.sub(
    r"def fetch_details_with_retry\(api, max_retries=2\):\n(?:    .*\n)+?\n\ndef run_pipeline",
    '''def fetch_details_with_retry(api, record_ids, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return api.fetch_details(record_ids)
        except TransientServiceError:
            if attempt == max_retries:
                raise
    raise RuntimeError("unreachable")


def run_pipeline''',
    text,
    count=1,
)
text = re.sub(
    r"def run_pipeline\(api, max_retries=2\):\n(?:    .*\n)+?    return api.save\(enriched\)\n",
    '''def run_pipeline(api, max_retries=2):
    token = api.authenticate()
    record_ids = api.list_records(token)
    details = fetch_details_with_retry(api, record_ids, max_retries=max_retries)
    enriched = api.enrich(details)
    return api.save(enriched)
''',
    text,
    count=1,
)
source.write_text(text, encoding="utf-8")
print("Applied targeted step-local retry fix.")
__SKILL_EVOL_SOLVE_PY_0__
