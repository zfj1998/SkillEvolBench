---
name: document-diff-comparison
description: Compare two versions of a plain text or markdown document and produce a clear change report. Use this skill when the task is to load two document versions, identify additions, deletions, and modifications, and report each change with its location, original text, and new text. Focus on text-level diff comparison for plain text and markdown documents using basic line-by-line or paragraph-by-paragraph comparison.
metadata:
  environment: document-parsing-extraction-transformation
  skill_id: E4-LS4
  short-description: "Compare two versions of a document and produce a clear change report"
  version: "1.0"
---

# Document Diff Comparison

Use this workflow when two text documents need to be compared and the result should be a readable change report. The goal is to load both versions, compare them at the text level, report additions, deletions, and modifications, and finish with a short summary count.

Scope: text-level diff comparison for plain text and markdown documents.

## When to Use

Use this skill when:

- the user asks what changed between two drafts
- two plain text or markdown files need a diff report
- the task is to list additions, deletions, and modified text blocks
- the output should include locations and before/after text

## Diff Workflow

Follow these five steps.

### Step 1 — Load Both Document Versions

Read both versions and keep their text in order.

Example:

```python
def load_lines(path):
    with open(path) as f:
        return f.read().splitlines()
```

Make sure you know which file is:

- V1: original version
- V2: revised version

### Step 2 — Compare Line by Line or Paragraph by Paragraph

Use line-by-line comparison by default.

```python
import difflib

matcher = difflib.SequenceMatcher(a=v1_lines, b=v2_lines, autojunk=False)
opcodes = matcher.get_opcodes()
```

For long-form prose, paragraph-by-paragraph comparison may be easier to read. In that case, split the documents into paragraph blocks first and diff those blocks the same way.

Use:

- line-level comparison for structured text and markdown
- paragraph-level comparison for long prose

### Step 3 — Classify the Changes

Convert the diff output into three user-facing categories:

- addition: text in V2 but not in V1
- deletion: text in V1 but not in V2
- modification: text changed from V1 to V2

Example classification:

```python
def classify(tag):
    if tag == "insert":
        return "addition"
    if tag == "delete":
        return "deletion"
    if tag == "replace":
        return "modification"
    return None
```

Ignore `equal` blocks when building the report.

### Step 4 — Report Each Change Clearly

For each non-equal block, report:

- location
- original text
- new text

Example output:

```text
Change 1 — modification
Location: V1 line 12 -> V2 line 12
Original: The deadline is March 15.
New: The deadline is April 1.
```

```text
Change 2 — addition
Location: V2 lines 20-22
Original: (empty)
New: ## Budget
     Phase 1: $50,000
     Phase 2: $30,000
```

If several nearby changes belong together, group adjacent changes into one logical block so the report is easier to read.

### Step 5 — Summarize Totals

End with a short summary:

- total additions
- total deletions
- total modifications

Example:

```text
Summary
- Additions: 2
- Deletions: 1
- Modifications: 3
```

## Basic Implementation Pattern

```python
import difflib

def diff_documents(v1_lines, v2_lines):
    matcher = difflib.SequenceMatcher(a=v1_lines, b=v2_lines, autojunk=False)
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        kind = {
            "insert": "addition",
            "delete": "deletion",
            "replace": "modification",
        }[tag]

        changes.append({
            "kind": kind,
            "v1_range": (i1 + 1, i2) if i1 != i2 else None,
            "v2_range": (j1 + 1, j2) if j1 != j2 else None,
            "original_text": "\n".join(v1_lines[i1:i2]),
            "new_text": "\n".join(v2_lines[j1:j2]),
        })

    return changes
```

## Practical Rules

### Use `difflib` Instead of Ad Hoc Matching

`difflib` already gives you stable text comparison behavior for basic document diffs.

### Ignore Whitespace-Only Changes When Requested

If the task says to ignore formatting noise, compare stripped text when filtering changes.

Example:

```python
def whitespace_only(change):
    return change["original_text"].strip() == change["new_text"].strip()
```

### Keep Locations in the Report

Line or paragraph locations make the change report much easier to check against the original documents.

### Group Nearby Changes When Helpful

Several adjacent edits are often easier to understand as one change block than as many tiny entries.

## Common Pitfalls

- forgetting which file is V1 and which is V2
- mixing additions and modifications in the report
- reporting raw diff output without readable locations
- treating whitespace-only edits as meaningful when they should be ignored
- splitting one local change into too many tiny report entries

## When NOT to Use

- the task needs a more advanced comparison than basic text diffing
- the files are not plain text or markdown documents
- the user wants a higher-level interpretation instead of a text change report

## Quick Summary

```text
1. Load both document versions
2. Compare them line by line or paragraph by paragraph
3. Classify changes as additions, deletions, or modifications
4. Report each change with location, original text, and new text
5. Summarize the total counts
```
