---
name: merge-conflict-resolution
description: Resolve git merge conflicts in Python and JavaScript code by combining changes from two branches correctly. Use this skill when `git merge` reports conflicted files, when a file contains conflict markers like `<<<<<<<`, `=======`, and `>>>>>>>`, or when the user asks for help merging two branches without discarding either side's important changes. Focus on conflicts that git reports explicitly in source files with conflict markers.
metadata:
  environment: code-debugging-modification
  skill_id: E1-LS5
  short-description: "Resolve git merge conflicts in Python and JavaScript code by combining changes from two branches correctly"
  version: "1.0"
---

# Merge Conflict Resolution

Use this workflow when git reports a merge conflict and leaves conflict markers inside Python or JavaScript files. The goal is to preserve the important intent from both branches and produce one coherent final version that still passes tests.

Scope: merge conflicts with explicit conflict markers in Python and JavaScript source files.

## When to Use

Use this skill when:

- `git merge <branch>` reports one or more conflicted files
- A file contains `<<<<<<<`, `=======`, and `>>>>>>>`
- Two branches changed the same part of a Python or JavaScript file
- The user needs help combining both sides rather than choosing one entire file

## Merge Workflow

Follow these six steps in order.

### Step 1 — Run the Merge and Read the Conflict Report

Start from the merge command and record which files are unresolved.

```bash
git merge <branch-name>
```

Useful follow-up commands:

```bash
git status
git diff --name-only --diff-filter=U
```

Your first task is to build the list of conflicted files. Do not begin editing until you know the full set.

### Step 2 — Open Each File and Find the Conflict Markers

In each conflicted file, locate every conflict block.

Conflict markers look like this:

```text
<<<<<<< HEAD
# current branch version
=======
# incoming branch version
>>>>>>> feature-branch
```

Read the markers literally:

- `<<<<<<< HEAD` starts the current branch section
- `=======` separates the two versions
- `>>>>>>> branch-name` ends the incoming branch section

A single file may contain multiple conflict blocks. Search for `<<<<<<<` to make sure you resolve every one.

### Step 3 — Understand What Both Sides Changed

Before editing, determine what each side was trying to do.

Useful commands:

```bash
git log --oneline HEAD -- <file>
git log --oneline <branch-name> -- <file>
git diff --ours -- <file>
git diff --theirs -- <file>
```

At each conflict block, ask:

1. What did the current branch add, remove, or change?
2. What did the incoming branch add, remove, or change?
3. Are these changes complementary or competing?

Typical cases:

- One side added a feature while the other fixed a bug
- Both sides changed the same function in different ways
- Both sides added imports needed by their new code
- One side renamed code while the other edited the old location

Do not guess from the conflict markers alone if the surrounding intent is unclear. Use git history and diff output to understand why the code changed.

### Step 4 — Edit the File to Combine Both Changes

Resolve each block by writing the final merged code and removing all conflict markers.

General rule: keep the behavior each branch needs, not the marker layout git produced.

#### Import conflicts

If both sides added different imports, keep the imports required by the merged result.

Python example:

```python
import logging
from utils import calculate_total, validate_input, format_currency
```

JavaScript example:

```javascript
import { useState, useEffect, useCallback } from "react";
import { fetchUser, updateUser } from "../api/users";
```

#### Function-level conflicts

If both sides changed the same function, merge the logic manually.

Example pattern:

- one side adds validation
- the other adds logging
- the merged result should usually include both validation and logging

Avoid replacing the whole file with one side if the final function needs logic from both versions.

### Step 5 — Verify the Merge by Running Tests

After all conflicted files are resolved, run the project's test suite.

Examples:

```bash
pytest --tb=short
```

```bash
npm test
```

Check for:

- syntax errors from incomplete marker removal
- missing imports after combining code
- broken function calls after merging logic
- duplicate declarations introduced during manual resolution

The merge is not complete until the code builds or tests cleanly again.

### Step 6 — Stage and Commit the Merge

Once the merged code is correct:

```bash
git add <resolved-files>
git commit
```

Before committing, confirm that:

- all conflict markers are gone
- all conflicted files are staged
- tests pass

## Helpful Techniques

### Compare Both Sides Clearly

Use these views when the markers alone are hard to interpret:

```bash
git diff --ours -- <file>
git diff --theirs -- <file>
```

They help you see each branch's edits more clearly than the raw marker block.

### Search for Unresolved Markers

Before staging, verify that no marker remains anywhere:

```bash
grep -rn "<<<<<<<\\|=======\\|>>>>>>>" --include="*.py" --include="*.js" .
```

### Be Careful With Full-File Replacement

Commands that take only the current or incoming version of an entire file can be useful in narrow cases, but they are not appropriate when the correct result needs code from both sides. Prefer manual block-by-block resolution for mixed changes.

## Common Pitfalls

- Resolving one conflict block without understanding the surrounding change
- Keeping only one branch when the correct result needs logic from both
- Forgetting a second or third conflict block later in the same file
- Removing markers but leaving imports, calls, or return values inconsistent
- Committing before running tests on the merged result

## When NOT to Use

- The file has no conflict markers and git is not reporting an unresolved merge
- The user is asking about a local code refactor rather than a real merge conflict
- The issue is a build or environment problem unrelated to merging two branches

## Quick Summary

```text
1. Run merge and list conflicted files
2. Find every conflict marker block
3. Understand what each branch changed
4. Manually combine both sides into one final version
5. Run tests on the merged code
6. Stage and commit the merge
```
