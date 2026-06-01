---
name: retry-and-backoff
description: Retry synchronous REST API calls when server errors occur. Use this skill when an HTTP request may temporarily fail with a 5xx response and the caller needs a simple retry loop with a fixed delay between attempts. Focus on straightforward retry handling for synchronous API calls with status-code-based decision rules.
metadata:
  environment: multi-step-tool-api-orchestration
  skill_id: E2-LS2
  short-description: "Retry synchronous REST API calls when server errors occur"
  version: "1.0"
---

# Retry and Backoff

Use this workflow when a synchronous API request may fail temporarily with a server error and needs a simple retry loop. The strategy here is deliberately basic: retry 5xx responses with a fixed wait, stop after a small number of attempts, and never retry 4xx responses.

Scope: simple fixed-delay retry for synchronous HTTP calls.

## When to Use

Use this skill when:

- A request can return transient server errors such as `500`, `502`, `503`, or `504`
- The caller needs a basic retry loop with a small fixed delay
- The request is synchronous and you want easy-to-read retry behavior
- The user asks for retry logic around an HTTP request

## Retry Workflow

Follow this five-step rule set for each request.

### Rule 1 — Make the API Call

Send the request once and inspect the response status before processing the result.

Always check the status code first. Do not assume the response body is safe to use until the request is classified as success.

### Rule 2 — If the Status Is 5xx, Wait and Retry

If the server responds with a 5xx status, treat it as retryable.

Examples:

- `500 Internal Server Error`
- `502 Bad Gateway`
- `503 Service Unavailable`
- `504 Gateway Timeout`

Use a fixed delay between attempts, such as `2` seconds.

### Rule 3 — Retry Up to 3 Times

Use `3` attempts as the default maximum.

If the request still fails with a retryable error after the final attempt, stop retrying and return the final error details.

### Rule 4 — If the Status Is 2xx, Process Normally

If the response is successful, return or process the result immediately.

Examples:

- `200 OK`
- `201 Created`
- `204 No Content`

No retry is needed after a successful response.

### Rule 5 — If the Status Is 4xx, Fail Immediately

If the response is a client error, do not retry.

Examples:

- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`

These errors usually mean the request itself is wrong, so retrying the same request will not help.

## Basic Implementation Pattern

The retry logic should:

1. make the request
2. inspect the status code
3. return immediately on `2xx`
4. fail immediately on `4xx`
5. sleep and retry on `5xx`
6. stop after the maximum retry count

Example shape:

```python
import requests
import time
import logging

def request_with_retry(method, url, max_retries=3, delay=2.0, **kwargs):
    for attempt in range(1, max_retries + 1):
        logging.info(f"Attempt {attempt}/{max_retries}: {method} {url}")
        response = requests.request(method, url, **kwargs)

        if 200 <= response.status_code < 300:
            logging.info(f"Attempt {attempt} succeeded with HTTP {response.status_code}")
            return response

        if 400 <= response.status_code < 500:
            raise Exception(f"Client error: HTTP {response.status_code}")

        if response.status_code >= 500:
            logging.warning(
                f"Attempt {attempt} failed with HTTP {response.status_code}; waiting {delay}s"
            )
            if attempt < max_retries:
                time.sleep(delay)
                continue
            raise Exception(f"All {max_retries} attempts failed. Last error: HTTP {response.status_code}")
```

## Logging Expectations

Log each retry attempt clearly.

Recommended details:

- attempt number
- total allowed attempts
- request method and URL
- response status
- fixed wait time before the next retry

Example log flow:

```text
INFO  Attempt 1/3: GET https://api.example.com/users
WARN  Attempt 1 failed with HTTP 503; waiting 2.0s
INFO  Attempt 2/3: GET https://api.example.com/users
INFO  Attempt 2 succeeded with HTTP 200
```

## Final Error Reporting

If all retries fail, include the final error details in the error report.

Good final error details include:

- attempt count
- last status code
- request target

Example:

```text
All 3 attempts failed. Last error: HTTP 503
```

This is more useful than a generic message like `request failed`.

## Status-Code Handling Summary

| Status class | Action |
|---|---|
| `2xx` | Success, process result |
| `4xx` | Report immediately, do not retry |
| `5xx` | Wait fixed delay, retry until limit |

## Common Pitfalls

- Processing the response body before checking the status code
- Retrying `4xx` errors even though the request itself is invalid
- Forgetting to log which retry attempt is running
- Letting the retry loop run indefinitely instead of stopping at the retry limit
- Returning a final error without including the last status code

## When NOT to Use

- The request does not need retry behavior at all
- The failure is not an HTTP response error
- The task requires more advanced retry coordination than a simple fixed-delay loop

## Quick Summary

```text
1. Make the API call
2. If 2xx, process normally
3. If 4xx, fail immediately
4. If 5xx, wait a fixed delay and retry
5. Stop after 3 attempts and report the final error
```
