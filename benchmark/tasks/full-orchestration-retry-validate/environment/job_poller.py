from __future__ import annotations

import time

import mock_api

POLL_INTERVAL_SECONDS = 0.55


def poll_until_completed(api, task_id: str, headers: dict[str, str]) -> dict[str, object]:
    while True:
        try:
            status = api.get_job_status(task_id, headers)
        except mock_api.ApiError as exc:
            if exc.status_code == 503:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            raise
        if status['status'] == 'completed':
            return status
        time.sleep(POLL_INTERVAL_SECONDS)
