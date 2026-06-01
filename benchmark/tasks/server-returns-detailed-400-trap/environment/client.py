import json
from pathlib import Path

from backend_selector import resolve_backend
from error_presenter import build_local_error
from local_rules import validate_payload
from remote_error_adapter import extract_remote_error

backend = resolve_backend()


def process_requests(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    successes = []
    failures = []
    backend.TRACE.clear()
    for item in payload:
        local_errors = validate_payload(item)
        if local_errors:
            failures.append(build_local_error(local_errors[0]))
            continue
        response = backend.call_api(item)
        if response["status"] == 400:
            failures.append(extract_remote_error(response))
            continue
        successes.append(response["body"]["payload"])
    return {"successes": successes, "failures": failures, "trace": list(backend.TRACE)}
