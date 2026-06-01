---
name: multi-file-bug-fix
description: Trace and fix bugs that span multiple files in Python and JavaScript projects. Use this skill when the visible symptom appears in one file but the root cause is likely upstream or downstream in another file, and the fix requires coordinated updates across several files. Trigger when a user reports wrong output, a broken flow, a changed function contract, a module move, or any bug where one local edit is unlikely to be enough. Focus on projects with roughly 4-7 files involved in the debugging path.
metadata:
  environment: code-debugging-modification
  skill_id: E1-LS4
  short-description: "Trace and fix bugs that span multiple files in Python and JavaScript projects"
  version: "1.0"
---

# Multi-File Bug Fix

Use this workflow when the symptom is visible in one file, but the real problem may be in another file in the call chain or data flow. The goal is not to patch the surface symptom. The goal is to find the true source of the bad data or broken contract and update every affected file.

Scope: Python and JavaScript projects with roughly 4-7 files involved in the fix.

## When to Use

Use this skill when:

- A function returns the wrong value, but the local code looks reasonable.
- A bug appears after a change to a shared function, module, or data shape.
- Fixing one file would likely break callers, imports, or downstream logic.
- A schema, model, helper, or utility change needs coordinated updates elsewhere.
- The user describes a bug that clearly crosses module boundaries.

## Multi-File Workflow

Follow these six steps in order.

### Step 1 — Start From the Symptom

Identify the exact place where the bug is observed.

Capture:

1. The file and function where the symptom shows up
2. The concrete bad output, failed assertion, or incorrect behavior
3. The input or path that reproduces it

Your starting point is the symptom location, not the assumed root cause.

Examples of useful symptom statements:

- "`render_summary()` in `views/order_summary.py` shows total = 0"
- "`formatUser()` returns an object missing the expected field"
- "The API handler works until `get_order_total()` is called"

### Step 2 — Trace the Data Flow Backward

Starting from the symptom, ask: where did this bad value come from?

Work backward one step at a time:

1. Open the file where the symptom appears.
2. Identify which function or module supplied the bad input.
3. Open that upstream file.
4. Repeat until you find the first place where correct input becomes incorrect output.

Useful search patterns:

```bash
grep -rn "function_name" --include="*.py" --include="*.js" src/ tests/
grep -rn "variable_name" --include="*.py" --include="*.js" src/ tests/
```

At each link, check:

- What data comes in
- What transformation happens
- What data goes out

The root cause is the step where the transformation stops matching what the next file expects.

### Step 3 — Trace the Data Flow Forward

Once you think you found the root cause, move in the other direction.

Ask: if I change this file, what else consumes its output?

Check:

- Direct callers of the changed function
- Downstream functions using its return value
- Files importing the module you plan to edit
- Tests and mocks that assume the old behavior

Helpful searches:

```bash
grep -rn "from module_name import" --include="*.py" src/ tests/
grep -rn "require.*moduleName\\|from.*moduleName" --include="*.js" src/ tests/
```

The purpose of forward tracing is to find the blast radius before you edit, not after tests fail.

### Step 4 — Identify Every File That Must Change

Before making edits, build a complete change list.

Typical categories:

- Root cause file
- Direct callers
- Downstream consumers
- Import or export locations
- Tests

If a function signature or return shape changes, update every caller in the same fix. Do not leave the codebase in a mixed old/new state.

A good change list answers:

- Which file contains the actual bug?
- Which files depend on that interface?
- Which tests or mocks will need updating?

### Step 5 — Make Coordinated Changes

Edit files from the center outward.

Recommended order:

1. Fix the root cause file.
2. Update direct callers.
3. Update downstream consumers.
4. Update imports or module references if needed.
5. Update unit tests and integration tests.

Keep the code consistent across all touched files:

- Function names match their new usage
- Parameters and return values match caller expectations
- Imports point to the correct module
- Shared data assumptions stay aligned across the changed path

If the bug involves a database field or model shape, verify that the change is reflected in both the model layer and the query or service layer.

### Step 6 — Run the Full Test Suite

Multi-file fixes should be verified with more than a narrow unit test.

Run:

1. The affected targeted tests
2. Integration tests covering the full path if the project has them
3. The full test suite before finishing

Examples:

```bash
pytest tests/integration/ -v
pytest
```

```bash
npm test -- --testPathPattern="integration"
npm test
```

If the project lacks an integration test for the affected flow, add one when practical. Multi-file fixes often pass isolated unit tests while still breaking the full path.

## What to Check During the Fix

### Callers and Imports

Whenever you change a shared function or move code between modules, re-check:

- all call sites
- all imports
- any re-export locations
- any test doubles or mocks

### Data Flow Consistency

Across the touched files, verify that:

- inputs match what callees expect
- outputs match what callers consume
- helpers and services agree on the same interface

### Test Coverage

For multi-file fixes, tests should exercise the real path across files, not only one local helper in isolation.

## Common Pitfalls

- Patching the symptom file without tracing where the bad value originated
- Fixing the root cause but forgetting callers or consumers
- Updating production code but leaving tests or mocks on the old contract
- Running only one narrow unit test after a cross-file change
- Making the change list after editing instead of before editing

## When NOT to Use

- The bug is clearly local to one file and does not affect callers or consumers.
- The task is a pure refactor without a real bug to fix.
- The issue is primarily environment setup rather than code behavior across files.

## Quick Summary

```text
1. Start from the visible symptom
2. Trace backward to find the first bad transformation
3. Trace forward to find the blast radius
4. List every file that must change
5. Update the root cause and all affected files together
6. Verify with integration coverage and the full test suite
```
