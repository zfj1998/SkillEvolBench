---
name: pre-call-parameter-validation
description: Validate REST API request parameters locally before sending the request. Use this skill when parameters come from user input, config, or upstream code and an invalid request would waste quota or fail predictably. Focus on single-request validation for required fields, types, ranges, enums, and string formats before making the API call.
metadata:
  environment: multi-step-tool-api-orchestration
  skill_id: E2-LS1
  short-description: "Validate REST API request parameters locally before sending the request"
  version: "1.0"
---

# Pre-Call Parameter Validation

Use this workflow to validate request parameters locally before making a REST API call. The goal is to catch obvious invalid input before the request leaves the process.

Scope: single-request validation for REST APIs.

## When to Use

Use this skill when:

- Parameters come from user input, config, or upstream code.
- The API will predictably reject bad parameters.
- You want to fail fast and avoid wasting API quota.
- The request needs local checks for presence, type, range, enum, or format.

## Validation Workflow

Apply these five checks before the API call.

### Check 1 — Required Fields

Verify that every required parameter is present and non-empty.

Examples of invalid values for required fields:

- missing key
- `None`
- empty string

Typical error:

```python
{"field": "city", "error": "missing", "message": "Required field 'city' is missing"}
```

### Check 2 — Type Checking

Verify that each parameter has the expected type.

Common expected types:

- `str`
- `int`
- `float`
- `bool`

Examples:

- `days` should be `int`
- `verbose` should be `bool`
- `city` should be `str`

Type mismatches should be reported clearly instead of letting the API reject them later.

### Check 3 — Range Validation

For numeric parameters, verify that the value is inside the allowed range.

Examples:

- `days` must be between `1` and `14`
- `page` must be between `1` and `1000`
- `lat` must be between `-90` and `90`

If the value is numeric but outside the supported range, reject it locally and skip the request.

### Check 4 — Enum Validation

For parameters with a fixed set of allowed values, verify that the value is one of them.

Examples:

- `units` must be `metric` or `imperial`
- `status` must be `active`, `inactive`, or `pending`

Reject any value outside the allowed set with a structured error.

### Check 5 — Format Validation

For string parameters with a defined format, validate with regex or parser logic.

Common formats:

- email
- URL
- ISO date
- ISO datetime
- UUID

If the format is wrong, do not send the request.

## Schema-Driven Validation

Build validation around a reusable schema instead of writing one-off checks at each call site.

Example schema:

```python
WEATHER_API_SCHEMA = {
    "required": ["city", "days", "units"],
    "types": {
        "city": str,
        "days": int,
        "units": str,
    },
    "ranges": {
        "days": (1, 14),
    },
    "enums": {
        "units": ["metric", "imperial"],
    },
}
```

Example validator shape:

```python
def validate_params(params, schema):
    errors = []
    errors.extend(check_required(params, schema.get("required", [])))
    errors.extend(check_types(params, schema.get("types", {})))
    errors.extend(check_ranges(params, schema.get("ranges", {})))
    errors.extend(check_enums(params, schema.get("enums", {})))
    errors.extend(check_formats(params, schema.get("formats", {})))
    return len(errors) == 0, errors
```

This pattern keeps validation reusable across endpoints and easy to update when the API schema changes.

## Structured Error Objects

Return structured error objects, not only strings.

Recommended shape:

```python
{
    "field": "days",
    "error": "out_of_range",
    "message": "'days' must be between 1 and 14, got 30",
}
```

Useful error categories:

- `missing`
- `empty`
- `wrong_type`
- `out_of_range`
- `invalid_option`
- `invalid_format`

Structured errors are easier for callers to log, inspect, and test.

## What to Do After Validation

Decision rule:

- If validation succeeds, proceed with the API call.
- If validation fails, skip the API call and return or log the errors clearly.

Example pattern:

```python
is_valid, errors = validate_params(params, WEATHER_API_SCHEMA)
if not is_valid:
    return {"success": False, "errors": errors}

response = requests.get("https://api.example.com/weather", params=params, timeout=30)
return {"success": True, "data": response.json()}
```

The request should be sent only after local validation passes.

## Validate Before Each Call in a Loop

If the same API is called repeatedly in a loop, validate on every iteration because parameters may change from one call to the next.

Do not validate only once before the loop and assume later iterations are still valid.

## Common Pitfalls

- Sending the request before all local checks finish
- Returning a bare string error instead of a structured error object
- Forgetting to validate format after type passes
- Running range checks on values that never passed type validation
- Validating once outside a loop when parameters change per iteration

## When NOT to Use

- The request has no meaningful local validation rules.
- The issue is response handling rather than request parameter quality.
- The task is not a REST-style API request with explicit parameter fields.

## Quick Summary

```text
1. Check required fields
2. Check types
3. Check numeric ranges
4. Check enums
5. Check string formats
6. If valid, send request; if invalid, skip call and return structured errors
```
