---
name: response-validation-fallback
description: Validate REST API responses before using the data, and fall back to a secondary source when validation fails. Use this skill when an HTTP response must pass top-level checks for status code, content type, JSON parsing, and required top-level fields before the payload is trusted. Focus on simple response validation plus optional fallback handling.
metadata:
  environment: multi-step-tool-api-orchestration
  skill_id: E2-LS5
  short-description: "Validate REST API responses before using the data, and fall back to a secondary source when validation fails"
  version: "1.0"
---

# Response Validation and Fallback

Use this workflow when an API response must be validated before the code is allowed to use the payload. The goal is to reject obviously invalid responses early and either try a fallback source or return a clear failure.

Scope: top-level response validation for status code, content type, JSON structure, and required top-level fields.

## When to Use

Use this skill when:

- A request returns JSON data that must be validated before use
- The caller needs basic response checking rather than trusting the body immediately
- A fallback source may be available if the primary response fails validation
- The user asks for safer response handling around an HTTP request

## Validation Workflow

Run these four checks in order. If any check fails, stop validation and go to fallback handling.

### Check 1 — HTTP Status Code

Classify the response by status code before touching the body.

Simple rule:

- `2xx` = success
- `4xx` = client error
- `5xx` = server error

Example:

```python
if response.status_code < 200 or response.status_code >= 300:
    return validation_error("status_code", f"HTTP {response.status_code}")
```

Do not call `response.json()` until the status code passes this check.

### Check 2 — Content-Type

Verify that the `Content-Type` header matches what you expect.

For JSON APIs, the header should contain `application/json`.

Example:

```python
content_type = response.headers.get("Content-Type", "")
if "application/json" not in content_type:
    return validation_error("content_type", f"Unexpected Content-Type: {content_type}")
```

### Check 3 — JSON Parsing

Attempt to parse the body as JSON.

Always wrap parsing in `try/except`.

Example:

```python
try:
    data = response.json()
except Exception as e:
    return validation_error("json_parse", str(e))
```

If parsing fails, the response is invalid and should not be used.

### Check 4 — Required Top-Level Fields

After parsing succeeds, check that the expected top-level fields exist.

Example:

```python
required_fields = ["id", "name", "status"]
missing = [field for field in required_fields if field not in data]
if missing:
    return validation_error("required_fields", f"Missing fields: {missing}")
```

For array responses, validate the top-level structure first and then check the expected fields on a representative item if needed.

## Reusable Schema Definitions

Define expected schemas as dictionaries so the validation rules stay explicit and reusable.

Example:

```python
SCHEMAS = {
    "user_detail": {
        "expected_type": dict,
        "required_fields": ["id", "name", "email", "status"],
    },
    "users": {
        "expected_type": list,
        "required_fields": ["id", "name", "email", "status"],
    },
}
```

Using named schemas makes validation easier to reuse across endpoints.

## Fallback Workflow

When validation fails, follow this sequence.

### Step 1 — Log the Validation Failure

Record which check failed and what was received.

Useful details:

- validation check name
- error detail
- URL
- status code
- content type

Example:

```python
import logging

def log_validation_failure(check_name, detail, response):
    logging.error(
        f"Validation failed at {check_name}: {detail} | "
        f"URL={response.url} | "
        f"status={response.status_code} | "
        f"content_type={response.headers.get('Content-Type', '')}"
    )
```

### Step 2 — Try Fallback Source If Available

If a fallback source exists, try it next.

Examples of fallback sources:

- secondary API endpoint
- cache
- local snapshot file

Important rule: run the same validation checks on the fallback response.

Do not trust fallback data automatically just because it is secondary.

### Step 3 — Return a Clear Error If No Fallback Works

If there is no fallback, or the fallback also fails validation, return a clear structured error.

Example:

```python
{
    "success": False,
    "error": {
        "check": "required_fields",
        "message": "Missing fields: ['status']",
    },
    "data": None,
}
```

The caller should be able to see which validation check failed.

## Basic Implementation Pattern

A simple validation function looks like this:

```python
def validation_error(check, message):
    return {"ok": False, "check": check, "message": message}

def fetch_and_validate(response, required_fields):
    if response.status_code < 200 or response.status_code >= 300:
        return validation_error("status_code", f"HTTP {response.status_code}")

    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        return validation_error("content_type", f"Unexpected Content-Type: {content_type}")

    try:
        data = response.json()
    except Exception as e:
        return validation_error("json_parse", str(e))

    if isinstance(data, dict):
        missing = [field for field in required_fields if field not in data]
        if missing:
            return validation_error("required_fields", f"Missing fields: {missing}")

    return {"ok": True, "data": data}
```

And a simple fallback wrapper looks like this:

```python
def fetch_with_fallback(primary_response, fallback_response, required_fields):
    result = fetch_and_validate(primary_response, required_fields)
    if result["ok"]:
        return result

    if fallback_response is not None:
        fallback_result = fetch_and_validate(fallback_response, required_fields)
        if fallback_result["ok"]:
            return fallback_result

    return result
```

## Practical Rules

### Check Status Before Parsing

Status code validation comes before `response.json()`. Keep that order fixed.

### Wrap JSON Parsing

Never assume parsing succeeds. Always use `try/except`.

### Keep Required Fields Explicit

Define the required top-level fields before validation starts so the rules are visible and reusable.

## Common Pitfalls

- Calling `response.json()` before checking status code
- Trusting the `Content-Type` header without attempting JSON parsing
- Using parsed data before required-field validation completes
- Skipping validation on the fallback source
- Returning a generic failure message without saying which check failed

## When NOT to Use

- The response does not need JSON-style validation
- The task is about request validation rather than response validation
- There is no meaningful schema or field expectation for the response

## Quick Summary

```text
1. Check status code
2. Check Content-Type
3. Parse JSON with try/except
4. Check required top-level fields
5. If validation fails, log it
6. Try fallback if available, otherwise return a clear error
```
