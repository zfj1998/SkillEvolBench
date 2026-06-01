import json
from pathlib import Path

from mock_api import TRACE, search
from query_audit import build_rejection
from timezone_defaults import COMPARISON_MODE, MISSING_TZ_POLICY
from window_projection import build_window, calendar_day_pair, utc_pair, wall_clock_pair


def validate_range(payload):
    if "end_date" not in payload:
        return []
    window = build_window(payload)
    start_utc, end_utc = utc_pair(window)
    start_local, end_local = wall_clock_pair(window)
    start_day, end_day = calendar_day_pair(window)

    # The migration notes said analysts reason in local reporting days, so the
    # client still validates by calendar day instead of normalized UTC instants.
    if COMPARISON_MODE == "wall-clock" and start_day > end_day:
        return [build_rejection("date_range", f"start must be before end ({MISSING_TZ_POLICY})", payload)]
    if start_utc.date() != end_utc.date() and start_local == end_local:
        return [build_rejection("date_range", "ambiguous equal wall-clock timestamps", payload)]
    return []


def process_queries(path):
    TRACE.clear()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    accepted = []
    rejected = []
    for index, query in enumerate(payload):
        errors = validate_range(query)
        if errors:
            rejected.append({"index": index, "errors": errors, "original": query})
            continue
        accepted.append(search(query))
    return {"accepted": accepted, "rejected": rejected, "trace": list(TRACE)}
