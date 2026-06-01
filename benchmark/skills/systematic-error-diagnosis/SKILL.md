---
name: systematic-error-diagnosis
description: Systematically diagnose and fix runtime errors in multi-file Python and JavaScript/TypeScript projects. Use this skill when a task includes a traceback, stack trace, failing command, failing test, or clear crash across 3-7 source files and you need to trace the root cause through the call chain. Focus on failures with explicit error output or crashes. Trigger on requests like "fix the bug", "resolve the traceback", "debug this project", or "make the failing test pass" when the failure already points to a concrete runtime error.
metadata:
  environment: code-debugging-modification
  skill_id: E1-LS1
  short-description: "Systematically diagnose and fix runtime errors in multi-file Python and JavaScript/TypeScript projects"
  version: "1.0"
---

# Systematic Error Diagnosis

Use this workflow when the project already gives you a concrete failure: a traceback, stack trace, thrown exception, or crashing test. The goal is to move from raw error output to a verified minimal fix without guessing.

Scope: Python and JavaScript/TypeScript projects with roughly 3-7 files involved in the debugging path.

## When to Use

Use this skill when:

- The program crashes with a visible error message.
- A test fails because execution throws an exception.
- The failure spans multiple files and the crash site may not be the root cause.
- The user asks to debug a project that already has a traceback or stack trace.

## Diagnostic Workflow

Follow these six steps in order.

### Step 1 — Read the Error Output Carefully

Before opening source files, extract these facts from the failure output:

1. **Exception / error type**: `TypeError`, `KeyError`, `ReferenceError`, `ModuleNotFoundError`, and so on.
2. **Crash location**: the exact file and line where execution broke.
3. **Full call chain**: the path from entry point to crash site.

Do not paraphrase the error too early. Keep the original wording in view while debugging.

#### Reading Python tracebacks

Python shows the call chain from entry point to crash site, with the bottom frame being where it failed.

```text
Traceback (most recent call last):
  File "main.py", line 12, in <module>
    run_pipeline(data)
  File "pipeline.py", line 45, in run_pipeline
    result = transform(record)
  File "transform.py", line 22, in transform
    return record["date"].split("-")
TypeError: 'NoneType' object has no attribute 'split'
```

Read from the bottom up:

- `transform.py:22` is the crash site.
- `pipeline.py:45` is the immediate caller.
- `main.py:12` is the entry point.

#### Reading Node.js / TypeScript stack traces

Node usually shows the crash site near the top.

```text
TypeError: Cannot read properties of undefined (reading 'map')
    at formatRows (/src/formatter.ts:18:24)
    at processData (/src/processor.ts:42:10)
    at main (/src/index.ts:7:3)
```

Read from the top down:

- `formatter.ts:18` is where it broke.
- `processor.ts:42` is the caller.
- `index.ts:7` is the entry point.

### Step 2 — Examine the Crash Site

Open the file at the reported line and read a small window around it, roughly 10 lines before and after. Look for obvious local issues first:

- Wrong variable name
- Missing import
- Incorrect function signature
- Unhandled `None` / `undefined`
- Incorrect type coercion
- Simple index or key access mistake

If the bug is clearly local, fix only after you can explain why that line fails. If it is not clearly local, continue.

### Step 3 — Trace the Call Stack Upward

If the crash line looks reasonable, inspect the callers one frame at a time.

For each caller:

1. Open the file at the stack-trace line.
2. Check the arguments being passed.
3. Check whether the callee's assumptions match what the caller provides.
4. Move one frame higher if the caller still looks correct.

The root cause is often upstream from the crash site. Your job is to find the earliest bad input or incorrect assumption in the chain.

### Step 4 — Add Temporary Runtime Inspection

If reading the code still does not explain the failure, inspect runtime values at key points in the chain.

Use temporary print/log statements at:

- The top of the crashing function
- The immediate caller
- Any suspicious branch or conversion point

Python example:

```python
print(f"DEBUG transform: record={record!r}, type={type(record)}")
```

JavaScript / TypeScript example:

```javascript
console.log("DEBUG formatRows", rows);
```

Re-run the failing command or test and compare the observed values with what the crashing code expects.

#### Debugger alternative

When available, a debugger can replace print statements:

- Python: `breakpoint()` or pdb / IDE debugger
- Node.js: `node --inspect-brk` or IDE debugger

Set the breakpoint at or just before the crash line and inspect local variables plus caller frames.

Remove temporary debug instrumentation once you have found the cause.

### Step 5 — Make the Minimal Fix

After identifying the root cause, change only the code needed to fix it.

Typical fixes:

- Correct a variable name
- Add a missing import
- Guard a null access
- Pass the right argument
- Fix an off-by-one boundary
- Normalize a value before use

Do not refactor unrelated code while debugging. Extra edits make it harder to verify the fix and easier to introduce regressions.

### Step 6 — Verify the Fix

Run the existing test suite or the exact failing command again.

- Python: `pytest`, `python -m unittest`, or project-specific test command
- Node.js: `npm test`, `npx jest`, `npx mocha`, or project-specific test command

Verification checklist:

1. The original failure no longer occurs.
2. The relevant test now passes.
3. No new failures were introduced by the fix.
4. Temporary debug output has been removed.

If verification fails, return to Step 2 with the new evidence.

## Common Bug Patterns

| Pattern | Typical symptom | First place to inspect |
|---|---|---|
| Off-by-one | `IndexError`, out-of-range access | Loop boundaries, slice endpoints, length checks |
| Wrong variable scope | `NameError`, `ReferenceError`, stale value | Local vs outer-scope declarations, shadowed names |
| Missing null check | `NoneType` / `undefined` property access | Value origin in caller, guard conditions |
| Incorrect type coercion | `TypeError`, invalid comparison | Conversion sites, input parsing, defaults |
| Wrong import path | `ModuleNotFoundError`, `Cannot find module` | Import statement, file location, package path |
| Wrong key / property name | `KeyError`, undefined property | Data shape at caller, object/dict construction |

## Common Pitfalls

- Editing code before you can point to the exact failing line and caller.
- Fixing the crash site when the bad input was created in an upstream file.
- Leaving debug prints in the final change.
- Making cleanup or refactor edits in the same patch as the bug fix.
- Stopping after one passing check without re-running the actual failing path.

## Quick Summary

```text
1. Read the traceback or stack trace
2. Inspect the crash line
3. Trace callers upward
4. Print or breakpoint runtime values if needed
5. Make the minimal fix
6. Re-run tests or the failing command
```
