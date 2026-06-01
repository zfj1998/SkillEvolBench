from __future__ import annotations

from rate_limit_policy import compute_wait_seconds, should_retry
from request_journal import journal_attempt


def fetch_cases(case_ids, api, clock, max_retries=3):
    results = {}
    history = []
    for case_id in case_ids:
        attempts = 0
        while True:
            response = api.get_resource(case_id, clock)
            status = response["status"]
            history.append(journal_attempt(case_id, attempts, response))
            if status == 200:
                results[case_id] = response["body"]
                break
            if should_retry(status, attempts, max_retries):
                attempts += 1
                clock.sleep(compute_wait_seconds(response["headers"], case_id))
                continue
            raise RuntimeError(f"request failed for {case_id}: {status}")
    return results
