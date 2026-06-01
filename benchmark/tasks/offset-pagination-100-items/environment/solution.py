from __future__ import annotations

import json
from pathlib import Path

from mock_api import build_api
from offset_plan import DEFAULT_LIMIT, build_request, next_offset, should_continue
from retrieval_audit import looks_complete
from user_buffer import merge_page

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    offset = 0
    limit = DEFAULT_LIMIT
    users = []
    expected_total = None

    while True:
        request = build_request(offset=offset, limit=limit)
        response = api.fetch_users(**request)
        expected_total = response["total"]
        merge_page(users, response["data"])
        if not should_continue(response):
            break
        offset = next_offset(offset, response, limit)

    if not looks_complete(len(users), expected_total):
        raise ValueError(f"expected {expected_total} users, got {len(users)}")
    return users


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
