---
name: result-sanity-reconciliation
description: Verify processed tabular results with basic sanity checks before using or returning them. Use this skill after a pandas or SQL data-processing pipeline when you need to confirm that the final output has a reasonable row count, contains the expected columns, looks plausible in sample rows, and does not contain unexpected NaN values in critical fields. Focus on simple final-output verification with df.shape, df.columns, df.describe(), and df.isna().sum().
metadata:
  environment: data-processing-structured-query
  skill_id: E3-LS5
  short-description: "Verify data processing results with basic sanity checks"
  version: "1.0"
---

# Result Sanity Reconciliation

Use this workflow after a data-processing pipeline produces a final table or DataFrame. The goal is to run a few fast checks before trusting or returning the result.

Scope: simple output verification for row count, column presence, sample inspection, and unexpected nulls in important columns.

## When to Use

Use this skill when:

- a join, filter, or aggregation just produced a final result
- you want to confirm the output shape and columns look correct
- you want a quick sample-based review before returning the data
- you need to check whether important fields contain unexpected `NaN`

## Verification Workflow

Run these four checks on the final output.

### Check 1 — Row Count

Start by confirming the output has a reasonable number of rows.

Example:

```python
print(df.shape)
print(len(df))
```

Questions to ask:

- Is the result empty when you expected rows?
- Is the result size roughly plausible for the task?
- Does the row count clearly look too small or too large?

This is a basic sanity check, not a full diagnosis. If the row count looks suspicious, stop and review the pipeline before trusting the result.

### Check 2 — Expected Columns

Confirm that all expected columns are present in the output.

Example:

```python
print(df.columns)
```

If you know the expected schema, compare against it explicitly.

```python
expected_columns = ["id", "name", "email", "score"]
missing = set(expected_columns) - set(df.columns)
print(missing)
```

Missing columns usually mean the output was projected incorrectly, a rename did not happen as expected, or a join/filter removed something important.

### Check 3 — Sample Inspection

Look at the first and last few rows to catch obvious issues quickly.

Example:

```python
print(df.head())
print(df.tail())
```

If the output contains numeric columns, get a quick statistical summary.

```python
print(df.describe())
```

Use this check to notice obvious problems such as repeated-looking rows, surprising values, or a result that does not resemble the intended output.

### Check 4 — Null Check

Check whether important columns contain unexpected missing values.

Example:

```python
print(df.isna().sum())
```

If some columns are critical, inspect them directly.

```python
critical_columns = ["id", "name", "email"]
for col in critical_columns:
    if col in df.columns:
        print(col, df[col].isna().sum())
```

Unexpected `NaN` values in critical fields are a sign the final result should not be trusted yet.

## Basic Implementation Pattern

```python
def sanity_check_result(df, expected_columns=None, critical_columns=None):
    print("shape:", df.shape)
    print("columns:", list(df.columns))
    print(df.head())
    print(df.tail())
    print(df.isna().sum())

    if expected_columns is not None:
        missing = set(expected_columns) - set(df.columns)
        print("missing_columns:", sorted(missing))

    if critical_columns is not None:
        for col in critical_columns:
            if col in df.columns:
                print(f"{col}_nulls:", df[col].isna().sum())
```

Example usage:

```python
sanity_check_result(
    df=result_df,
    expected_columns=["id", "name", "email", "score"],
    critical_columns=["id", "name"]
)
```

## Practical Rules

### Start with `df.shape`

The fastest first check is whether the final result size even looks plausible.

### Check Columns Explicitly

Do not assume the right columns survived the pipeline. Print them or compare against a known expected list.

### Inspect Real Rows

`head()` and `tail()` often reveal problems faster than reading code.

### Check Nulls in Important Fields

`df.isna().sum()` is a quick way to see whether key output columns are missing values unexpectedly.

### Use Lightweight Debug Prints When Needed

Printing `df.shape` and `df.columns` after a major operation can help you understand how the final result was formed, but keep this skill focused on basic output verification.

## Common Pitfalls

- trusting the final output without checking its row count
- assuming expected columns are present without printing `df.columns`
- inspecting only one sample row instead of checking both `head()` and `tail()`
- forgetting to run `df.isna().sum()` on the final result
- skipping `df.describe()` when numeric columns look suspicious

## When NOT to Use

- the task is to debug a specific join or aggregation internally
- the main issue is schema discovery rather than final-result checking
- you need deeper reconciliation logic instead of basic sanity checks

## Quick Summary

```text
1. Print df.shape and confirm the row count looks reasonable
2. Print df.columns and check expected columns are present
3. Inspect df.head() and df.tail()
4. Use df.describe() for a quick numeric summary
5. Run df.isna().sum() and inspect critical columns for unexpected NaN
```
