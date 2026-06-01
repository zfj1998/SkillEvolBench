import json
from pathlib import Path

from batch_summary import build_summary
from duplicate_guard import freeze_username_snapshot
from mock_api import CREATED, create_account
from row_projection import project_row
from screening_policy import screen_candidate


def import_batch(path):
    CREATED.clear()
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    successes = []
    failures = []
    username_snapshot = freeze_username_snapshot(CREATED)
    for index, row in enumerate(rows):
        candidate = project_row(row, index)
        errors = screen_candidate(candidate, username_snapshot)
        if errors:
            failures.append({"row": candidate, "errors": errors})
            return {"success": successes, "failures": failures, "summary": build_summary(rows, successes, failures)}
        result = create_account(candidate)
        successes.append(result)
    return {"success": successes, "failures": failures, "summary": build_summary(rows, successes, failures)}
