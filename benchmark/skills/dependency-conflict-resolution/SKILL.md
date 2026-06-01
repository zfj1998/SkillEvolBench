---
name: dependency-conflict-resolution
description: Diagnose and resolve Python package version conflicts in pip-based projects. Use this skill when `pip install` fails with resolver errors, when `pip check` reports incompatible versions, or when a Python project's dependency graph contains conflicting version constraints that must be reconciled in `requirements.txt` or `pyproject.toml`. Focus on single-project pip workflows with explicit version conflicts and shared dependencies.
metadata:
  environment: code-debugging-modification
  skill_id: E1-LS2
  short-description: "Diagnose and resolve Python package version conflicts in pip-based projects"
  version: "1.0"
---

# Dependency Conflict Resolution

Use this workflow when a Python project's dependencies cannot be resolved cleanly by pip because packages require incompatible versions of the same library.

Scope: pip-based Python projects using `requirements.txt`, `pyproject.toml`, or `constraints.txt`.

## When to Use

Use this skill when:

- `pip install` fails with `ResolutionImpossible` or similar resolver output.
- Pip reports that one package requires a version range incompatible with another package.
- `pip check` reports installed packages with conflicting requirements.
- You already know the failure is a Python package version conflict and need to resolve it cleanly.

## Resolution Workflow

Follow these six steps in order.

### Step 1 — Read the Pip Error Message

Start with pip's resolver output. Extract these facts before changing any files:

1. **Conflicting packages**: which packages disagree.
2. **Version constraints**: the exact specifiers each package requires.
3. **Shared dependency**: the package being pulled in incompatible directions.

Typical message shape:

```text
Package X requires Y>=2.0, but you have Y==1.5 which is incompatible.
```

Write the constraints down exactly. Do not summarize them loosely. The difference between `>=2.0` and `~=2.0` matters.

### Step 2 — Map the Dependency Tree

Trace how the conflict is introduced.

Preferred tools:

- `pipdeptree` to visualize the dependency graph
- `pip show <package>` to inspect dependencies package by package

Your goal is to find the **conflict subgraph**:

```text
your-project
├── package-a -> shared-lib>=2.0
└── package-b -> shared-lib<2.0,>=1.5
```

Pay attention to transitive dependencies. The conflicting constraint is often introduced by a dependency of a dependency rather than a package listed directly in the project file.

### Step 3 — Check for a Compatible Version Window

Once you know all constraints on the shared dependency, compute whether they overlap.

Useful specifier reminders:

| Specifier | Meaning |
|---|---|
| `==1.8.0` | Exact version only |
| `>=1.5` | This version or higher |
| `<2.0` | Strictly below 2.0 |
| `!=1.7.0` | Any version except 1.7.0 |
| `~=1.5` | Compatible release range |

Use `pip index versions <package>` if you need to see which concrete versions exist.

Decision rule:

- If the constraint intersection is non-empty, choose a version in that window and continue to Step 5.
- If the intersection is empty, continue to Step 4.

Do not upgrade or downgrade packages before checking whether a shared compatible version already exists.

### Step 4 — Upgrade or Downgrade the Constraining Package

If no version can satisfy all constraints on the shared dependency, one of the top-level packages must change.

Work through this order:

1. Identify which top-level package imposes the tighter constraint.
2. Check whether a newer release of that package widens the dependency range.
3. If so, upgrade that top-level package.
4. If not, check whether the other top-level package can be downgraded to a compatible release.

Only change packages directly involved in the conflict. Avoid unrelated dependency churn while debugging.

### Step 5 — Write the Resolution into Project Files

Persist the fix in the project's dependency files. Do not treat a one-off shell install as the final resolution.

Update one or more of:

- `requirements.txt`
- `pyproject.toml`
- `constraints.txt`

What to write:

1. Pin the shared dependency if you found a compatible version window.
2. Pin the upgraded or downgraded top-level package if Step 4 required it.
3. Prefer explicit pins for the conflicting packages so the resolver does not drift later.

Example:

```text
shared-lib==1.8.0
package-a==2.4.1
```

### Step 6 — Verify, Then Lock

Verify the fix in this order:

1. Run a dry run first: `pip install --dry-run -r requirements.txt` or `pip install --dry-run -e .`
2. If the dry run succeeds, install in a clean environment.
3. Run `pip check` to confirm the installed environment is internally consistent.
4. Run the project's test suite.
5. Freeze the resolved environment to a lock-style file: `pip freeze > requirements.lock`

If the dry run still fails, return to Step 3 and re-check the constraint window.

## Common Pitfalls

- Pinning a shared dependency before confirming that **all** dependents accept that version.
- Reading only the top-level conflict message and ignoring transitive dependencies underneath it.
- Changing packages on the command line without writing the fix back to project files.
- Skipping `pip install --dry-run` and modifying the environment before checking the resolution.
- Forgetting to regenerate a lock-style file after the conflict is resolved.

## When NOT to Use

- The problem is a missing package rather than a version conflict.
- The failure is caused by a system library or compiler dependency rather than a Python package version.
- The project is not using pip-style dependency files for resolution.

## Quick Summary

```text
1. Read the pip resolver message
2. Map the dependency tree
3. Check whether version constraints overlap
4. Upgrade or downgrade the constraining top-level package if needed
5. Persist the fix in requirements.txt / pyproject.toml / constraints.txt
6. Dry-run, install, test, and lock
```
