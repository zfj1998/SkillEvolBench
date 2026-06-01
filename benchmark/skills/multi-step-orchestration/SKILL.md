---
name: multi-step-orchestration
description: Chain two API calls into a simple workflow where the output of the first call is used as input for the second call. Use this skill when a request pattern looks like authenticate then fetch, look up an ID then retrieve details, or any other two-step sequence where Call B depends directly on a value extracted from Call A. Focus on simple two-step API chains only.
metadata:
  environment: multi-step-tool-api-orchestration
  skill_id: E2-LS4
  short-description: "Chain two API calls into a simple workflow where the output of the first call is used as input for the second call"
  version: "1.0"
---

# Multi-Step Orchestration

Use this workflow when an API task has exactly two dependent calls: the first call returns a value that the second call needs. The pattern is simple and fixed: call A, extract a value, call B with that value, then return the final result.

Scope: simple two-step API chains.

## When to Use

Use this skill when:

- The second API call depends directly on data from the first call
- The first call returns a token, ID, endpoint, or other lookup value
- The user asks for an authenticate-then-fetch or lookup-then-fetch flow
- The orchestration is a single A-then-B dependency chain

## Two-Step Workflow

Follow this pattern:

```text
Call A
  ↓
Extract needed value
  ↓
Call B using that value
  ↓
Return final result
```

## Step 1 — Make the First API Call

Send the first request and capture its response.

Examples:

- authenticate and get an access token
- look up a user by email and get a user ID
- search for a record and get its primary key

The output of Step 1 is not the final result. Its main job is to provide the value needed for Step 2.

## Step 2 — Extract the Needed Value

After Step 1 succeeds, extract the specific field needed by the second call.

Common intermediate values:

- `access_token`
- `user_id`
- `order_id`
- `resource_url`

Validate the extracted value before using it:

- make sure the field exists
- make sure it is not null or empty
- make sure it has the expected type

Do not pass an unchecked intermediate value into Step 2.

## Step 3 — Make the Second API Call

Use the extracted value as input to the second request.

Examples:

- `Authorization: Bearer <token>`
- `GET /users/<user_id>`
- `GET /orders/<order_id>`

The second request should use the value from Step 1 through a variable, not a hardcoded placeholder.

## Step 4 — Process and Return the Final Result

If Step 2 succeeds, return its result as the workflow output.

The final output of the two-step chain is the successful result of Call B, not the intermediate payload from Call A.

## Error Handling Rules

Use these rules between steps:

- If Step 1 fails, do not attempt Step 2.
- If Step 1 succeeds but extraction fails, stop and report the extraction problem clearly.
- If Step 2 fails, report the Step 2 error and include the intermediate value from Step 1 when useful for debugging.

Typical examples:

- `Step 1 failed: HTTP 401`
- `Step 1 succeeded but response missing 'user_id'`
- `Step 2 failed: HTTP 404 for user_id=12345`

## Basic Implementation Pattern

A simple structure looks like this:

```python
import logging
import requests

def get_user_details_by_email(email):
    logging.info(f"Step 1 input: email={email}")
    step1 = requests.get(
        "https://api.example.com/users/search",
        params={"email": email},
        timeout=30,
    )

    logging.info(f"Step 1 output: status={step1.status_code}")
    if step1.status_code != 200:
        return {"success": False, "error": f"Step 1 failed: HTTP {step1.status_code}"}

    step1_data = step1.json()
    user_id = step1_data.get("user_id")
    if user_id is None:
        return {"success": False, "error": "Step 1 succeeded but response missing 'user_id'"}

    logging.info(f"Step 2 input: user_id={user_id}")
    step2 = requests.get(
        f"https://api.example.com/users/{user_id}",
        timeout=30,
    )

    logging.info(f"Step 2 output: status={step2.status_code}")
    if step2.status_code != 200:
        return {"success": False, "error": f"Step 2 failed: HTTP {step2.status_code} for user_id={user_id}"}

    return {"success": True, "data": step2.json()}
```

## Logging Guidance

Log each step's input and output clearly.

Useful details to log:

- Step 1 input
- Step 1 status code
- extracted intermediate value
- Step 2 input
- Step 2 status code

This makes debugging straightforward when the chain breaks between steps.

## Practical Rules

### Pass Data Through Variables

Store the extracted value from Step 1 in a variable and pass it into Step 2.

Good:

```python
token = auth_data["access_token"]
headers = {"Authorization": f"Bearer {token}"}
```

Bad:

```python
headers = {"Authorization": "Bearer hardcoded-token"}
```

### Validate the Intermediate Value

Treat the extracted value as an interface boundary. Validate it before Step 2 so the error is caught at the handoff point instead of surfacing later as a confusing downstream failure.

### Keep the Chain Sequential

The second call must happen only after the first call succeeds and the needed value is extracted successfully.

## Common Pitfalls

- Hardcoding the Step 2 input instead of using the Step 1 result
- Skipping validation of the intermediate value
- Running Step 2 even after Step 1 failed
- Logging too little detail to tell which step broke
- Returning the Step 1 payload instead of the final Step 2 result

## When NOT to Use

- The workflow is not a two-step dependency chain
- The second request does not depend on data from the first
- The task is only one API call with no orchestration at all

## Quick Summary

```text
1. Call API A
2. Extract and validate the needed value
3. Call API B using that value
4. If A fails, stop
5. If B fails, report B's error with A's context
6. Return B's result on success
```
