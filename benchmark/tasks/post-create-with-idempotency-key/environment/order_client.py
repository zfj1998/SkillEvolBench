from __future__ import annotations

from request_envelope import build_create_request
from request_journal import note_timeout


def create_order(body, api, max_attempts=2):
    attempts_log = []
    for attempt in range(max_attempts):
        headers, payload = build_create_request(body)
        try:
            response = api.create_order(payload, headers=headers)
            return response["body"]["order"]
        except TimeoutError:
            attempts_log.append(note_timeout(attempt))
            if attempt == max_attempts - 1:
                raise
    raise RuntimeError("unreachable")
