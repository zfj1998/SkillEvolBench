---
name: safe-refactoring
description: Safely restructure Python code to improve clarity, reduce duplication, and increase maintainability without changing external behavior. Use this skill when the user asks to refactor, clean up, simplify, rename, extract functions or classes, remove dead code, or reorganize Python code while keeping the existing behavior intact. Focus on Python projects with an existing test suite and structural changes only.
metadata:
  environment: code-debugging-modification
  skill_id: E1-LS3
  short-description: "Safely restructure Python code to improve clarity, reduce duplication, and increase maintainability without changing external behavior"
  version: "1.0"
---

# Safe Refactoring

Use this workflow when the goal is to improve code structure without adding features or changing behavior. Refactoring is successful only when the code is cleaner and the existing tests still pass.

Scope: Python codebases with an existing test suite.

## When to Use

Use this skill when:

- A function is too long or too complex.
- The same logic appears in multiple places.
- Names are vague or misleading.
- Conditionals are deeply nested.
- A module or class has too many responsibilities.
- The user asks for cleanup, simplification, extraction, or reorganization rather than a bug fix or new feature.

## Safety Protocol

Follow this loop for every refactoring step:

1. Run the existing test suite before editing to establish a green baseline.
2. Make one refactoring change only.
3. Run the test suite again immediately.
4. If tests fail, revert that change and investigate.
5. If tests pass, keep the change and commit it as a separate step.

Keep the loop tight. Do not combine multiple unrelated refactorings into one test run.

Baseline examples:

```bash
pytest --tb=short
```

After each step:

```bash
pytest --tb=short
git diff --stat
git commit -am "refactor: extract subtotal helper"
```

## Refactoring Techniques

### Technique 1 — Extract Function

Use this when a function contains a repeated or clearly separable block of logic.

Typical signs:

- The function is longer than about 50 lines.
- One block has a clear job with obvious inputs and outputs.
- The same calculation or validation appears in multiple places.

Target shape:

- Give the extracted function a specific name.
- Pass explicit parameters instead of relying on outer scope.
- Return only the value needed by the caller.

Example:

```python
def process_order(order):
    validate_order_items(order.items)
    subtotal = calculate_subtotal(order.items)
    tax = subtotal * order.tax_rate
    return subtotal + tax
```

Refactor one extraction at a time. If you extract validation logic and calculation logic, treat them as separate steps with separate test runs.

### Technique 2 — Rename for Clarity

Use this when names do not communicate intent.

Common bad names:

- `data`
- `tmp`
- `process`
- `handle`
- single-letter variables outside tiny local loops

Rename to match the real role of the value or function:

| Weak name | Better name |
|---|---|
| `data` | `user_records` |
| `tmp` | `filtered_items` |
| `process()` | `validate_and_save()` |
| `flag` | `is_authenticated` |

Rename across all call sites before running tests. Search first, then update every usage in code and tests.

Keep public function signatures stable unless you are deliberately updating all callers in the same refactoring step.

### Technique 3 — Remove Dead Code

Use this when code is clearly unused or unreachable.

Examples:

- Unused imports
- Unused local variables
- Commented-out old implementations
- Branches that can never execute
- Statements after `return`

Helpful tools:

```bash
ruff check src/ --select F401,F841
python -m pyflakes src/
```

Delete dead code in small steps. After each removal, run tests to confirm that the code really was unused.

### Technique 4 — Simplify Conditionals

Use this when control flow is harder to follow than it needs to be.

Preferred simplifications:

- Replace nested `if` blocks with guard clauses.
- Use early returns to flatten control flow.
- Replace long `if` / `elif` chains with lookup tables when the mapping is static.

Example:

```python
def get_discount(user, order):
    if user is None:
        return 0.0
    if not user.is_premium:
        return 0.05
    if order.total > 100:
        return 0.15
    return 0.10
```

The refactoring goal is clearer structure, not different logic.

### Technique 5 — Extract Class or Module

Use this when one file or class is doing too many jobs.

Typical signs:

- A file is very large, roughly 300+ lines.
- A class can only be described as doing "X and Y and Z".
- Methods in the same class do not operate on the same core state.

Split responsibilities into focused units:

- Move payment logic out of an order service.
- Move notification logic out of a business rules module.
- Break one large utility module into smaller domain modules.

Extract one class or module at a time. After each move:

1. Fix imports.
2. Update call sites.
3. Run tests.

## Code Smells to Look For

| Smell | Practical threshold | First technique to try |
|---|---|---|
| Long function | More than ~50 lines | Extract Function |
| Deep nesting | More than ~3 indentation levels | Simplify Conditionals |
| Duplicate logic | Same block in 2+ places | Extract Function |
| Vague naming | Generic names like `data`, `tmp`, `process` | Rename for Clarity |
| Large multi-role class | Roughly 300+ lines or several responsibilities | Extract Class/Module |
| Unused code | Imports, vars, branches, commented code | Remove Dead Code |

## How to Verify a Refactoring Step

After each step, inspect both tests and diff.

Test check:

- Baseline tests were green before the change.
- Tests are green after the change.

Diff check:

- Only intended files changed.
- The patch is small and understandable.
- No unrelated formatting churn was introduced.
- Public interfaces stayed stable unless all callers were updated in the same step.

Helpful commands:

```bash
git diff
git diff --stat
```

## Common Pitfalls

- Refactoring before establishing a passing test baseline.
- Combining extraction, rename, cleanup, and file moves in one large patch.
- Changing public interfaces accidentally while cleaning up internals.
- Removing code that only looks unused without checking callers or tests.
- Treating refactoring like feature work and slipping in behavior changes.

## When NOT to Use

- The user is asking for a bug fix rather than a structural cleanup.
- The code has no meaningful tests and behavior safety depends on those tests.
- The requested change is really a new feature or product behavior change.

## Quick Summary

```text
1. Run tests before any changes
2. Make one structural refactoring step
3. Run tests again immediately
4. Inspect the diff
5. Keep and commit only if still green
6. Repeat for the next technique
```
