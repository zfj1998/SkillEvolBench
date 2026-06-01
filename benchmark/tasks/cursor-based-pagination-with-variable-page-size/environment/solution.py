from __future__ import annotations

import json
from pathlib import Path

from cursor_contract import build_request, next_cursor
from event_buffer import append_events
from mock_api import build_api
from stream_audit import looks_complete

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output.json"
TRACE = HERE / "trace.json"


def solve(api):
    cursor = None
    events = []
    request_limit = 20

    while True:
        response = api.fetch_events(**build_request(cursor, limit=request_limit))
        append_events(events, response["data"])
        if next_cursor(response) is None:
            break
        cursor = next_cursor(response)

    if not looks_complete(len(events), 80):
        raise ValueError(f"expected 80 events, got {len(events)}")
    return events


def main():
    api = build_api()
    result = solve(api)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    TRACE.write_text(json.dumps(api.export_state(), indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
