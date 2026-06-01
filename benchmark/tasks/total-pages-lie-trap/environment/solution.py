from __future__ import annotations

import json
from pathlib import Path

from mock_api import build_api
from page_plan import build_fetch_plan
from report_cache import snapshot_metadata
from report_audit import looks_reasonable

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    first_page = api.get_reports(page=1)
    metadata = snapshot_metadata(first_page)
    reports = list(first_page["data"])

    for page in build_fetch_plan(first_page):
        response = api.get_reports(page=page)
        reports.extend(response["data"])

    if not looks_reasonable(len(reports)):
        raise ValueError(f"expected 80 reports, got {len(reports)}")
    return reports


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
