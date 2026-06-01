from __future__ import annotations

from auth_policy import classify_response
from token_session import bootstrap_token, refresh_token


def get_protected_data(api, clock, max_retries=3, pre_request_delay=0.0):
    token = bootstrap_token(api, clock)
    if pre_request_delay:
        clock.sleep(pre_request_delay)
    retries = 0
    while True:
        response = api.fetch_data(token, clock)
        action = classify_response(response)
        if action == "ok":
            return response["body"]
        if action == "refresh":
            token = refresh_token(api, clock)
            continue
        if action == "retry" and retries < max_retries:
            retries += 1
            continue
        raise RuntimeError(f"request failed: {response['status']}")
