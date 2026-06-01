from __future__ import annotations

from mock_pipeline import TransientServiceError


def fetch_details_from_stage(api, max_retries: int = 2):
    for attempt in range(max_retries + 1):
        token = api.authenticate()
        record_ids = api.list_records(token)
        try:
            return api.fetch_details(record_ids)
        except TransientServiceError:
            if attempt == max_retries:
                raise
    raise RuntimeError("unreachable")
