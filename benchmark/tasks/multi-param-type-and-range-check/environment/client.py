import json
from pathlib import Path

from mock_api import TRACE, fetch_weather
from preflight_policy import collect_validation_errors, prepare_candidate
from request_audit import build_failure_entry, summarize_batch
from request_routing import dispatch_weather_request


def validate_request(request):
    candidate = prepare_candidate(request)
    return collect_validation_errors(candidate)


def process_requests(path):
    TRACE.clear()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    successes = []
    failures = []
    for index, request in enumerate(payload):
        candidate = prepare_candidate(request)
        errors = validate_request(candidate)
        if errors:
            failures.append(build_failure_entry(index, candidate, errors))
            continue
        successes.append(dispatch_weather_request(candidate, fetch_weather))
    return summarize_batch(successes, failures, TRACE)
