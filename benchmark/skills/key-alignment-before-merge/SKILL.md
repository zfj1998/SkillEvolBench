---
name: key-alignment-before-merge
description: "Align join keys across data sources before merging. Use this skill when two tables or DataFrames need to be joined but the key columns may differ in name, dtype, or string casing. Focus on simple key alignment before merge - column name matching, type matching, case normalization, and basic merge-result validation."
metadata:
  environment: data-processing-structured-query
  skill_id: E3-LS3
  short-description: "Align join keys across data sources before merging"
  version: "1.0"
---

# Key Alignment Before Merge

Use this workflow before merging two tables or DataFrames when the join keys may not line up cleanly. The goal is to make the key columns compatible before the merge happens.

Scope: simple key alignment with column renaming, dtype matching, case normalization, and merge-result checking.

## When to Use

Use this skill when:

- a merge returns too few rows or too many `NaN` values
- the key columns have different names
- the key columns use different dtypes
- string keys may differ only by casing

## Alignment Workflow

Run these four steps before merging.

### Step 1 — Compare Key Column Names

Check whether the key column names match across both sources.

Example:

```python
print(df_left.columns)
print(df_right.columns)
```

If the keys use different names, rename one side to match the other.

Example:

```python
df_right = df_right.rename(columns={"user_id": "id"})
```

You can also merge with `left_on` and `right_on`, but renaming first usually keeps the merge cleaner.

### Step 2 — Compare Key Column Types

Check whether both key columns use the same dtype.

Example:

```python
print(df_left["id"].dtype)
print(df_right["id"].dtype)
```

If one side is numeric and the other is string, convert them to a common type before merging.

Examples:

```python
df_left["id"] = df_left["id"].astype(str)
df_right["id"] = df_right["id"].astype(str)
```

```python
df_left["id"] = df_left["id"].astype(int)
df_right["id"] = df_right["id"].astype(int)
```

The important point is not which type you choose. The important point is that both sides use the same type before the join.

### Step 3 — Normalize String Casing

If the join keys are strings, normalize casing on both sides.

Example:

```python
df_left["email"] = df_left["email"].str.lower()
df_right["email"] = df_right["email"].str.lower()
```

This avoids merge misses caused only by case differences such as:

- `Alice@Acme.com`
- `alice@acme.com`

Only do this when the key is intended to be case-insensitive.

### Step 4 — Check for NaN Keys and Merge

Before merging, check whether either side contains missing key values.

Example:

```python
print(df_left["id"].isna().sum())
print(df_right["id"].isna().sum())
```

Rows with missing join keys will not match during the merge.

Then perform the merge and inspect the row count.

Example:

```python
result = df_left.merge(df_right, on="id", how="inner")
print(len(result))
```

After the merge, ask whether the result size looks reasonable for the expected join.

## Basic Implementation Pattern

```python
def align_keys(df_left, df_right, left_key, right_key):
    if left_key != right_key:
        df_right = df_right.rename(columns={right_key: left_key})

    key = left_key

    if df_left[key].dtype != df_right[key].dtype:
        df_left[key] = df_left[key].astype(str)
        df_right[key] = df_right[key].astype(str)

    if df_left[key].dtype == "object":
        df_left[key] = df_left[key].str.lower()
        df_right[key] = df_right[key].str.lower()

    left_nan = df_left[key].isna().sum()
    right_nan = df_right[key].isna().sum()
    print(f"NaN keys: left={left_nan}, right={right_nan}")

    return df_left, df_right
```

Usage:

```python
df_left, df_right = align_keys(df_left, df_right, "id", "user_id")
result = df_left.merge(df_right, on="id", how="inner")
print(f"Merged rows: {len(result)}")
```

## Practical Rules

### Rename Before Merge

If the keys use different names, align the names first so the merge step stays simple and explicit.

### Match Dtypes Before Merge

Never assume pandas will align `int` and `str` keys automatically in a useful way. Convert them explicitly.

### Normalize String Keys on Both Sides

If you lowercase only one side, the mismatch remains. Apply the same normalization to both key columns.

### Check the Merge Result

A merge that technically runs can still be wrong. Always inspect whether the result row count is plausible.

## Common Pitfalls

- merging before checking whether the key columns even match by name
- converting only one side of the join key
- forgetting case normalization for string keys
- ignoring missing keys before the merge
- trusting the merge result without checking whether the row count makes sense

## When NOT to Use

- the keys are already aligned and the merge works as expected
- the task is about discovering which columns should be used as keys
- the issue is schema inspection rather than pre-merge key alignment

## Quick Summary

```text
1. Compare key column names and rename if needed
2. Compare key dtypes and convert to a common type
3. Lowercase string keys on both sides when appropriate
4. Check for NaN keys
5. Merge and confirm the row count is reasonable
```
