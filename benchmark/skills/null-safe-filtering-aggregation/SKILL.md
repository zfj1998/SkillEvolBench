---
name: null-safe-filtering-aggregation
description: Handle missing values correctly during data filtering and aggregation in pandas. Use this skill when a DataFrame contains NaN values and the task involves filtering rows, filling missing values, or computing aggregates such as mean, sum, or count. Focus on pandas NaN handling with isna(), dropna(), fillna(), and built-in aggregate functions before drawing conclusions from filtered or aggregated data.
metadata:
  environment: data-processing-structured-query
  skill_id: E3-LS4
  short-description: "Handle missing values correctly during data filtering and aggregation in pandas"
  version: "1.0"
---

# Null-Safe Filtering Aggregation

Use this workflow when a pandas DataFrame contains missing values and the result depends on filtering or aggregation. The goal is to inspect NaN values first, choose a simple handling strategy, and then compute aggregates without accidentally misreading the result.

Scope: pandas NaN handling with `dropna()`, `fillna()`, `isna()`, `notna()`, and built-in aggregate functions such as `mean()`, `sum()`, and `count()`.

## When to Use

Use this skill when:

- a column used for filtering contains `NaN`
- aggregate results look suspicious because rows are missing values
- you need to decide whether to drop or fill missing values
- you need to compare non-null counts against total row counts

## Null-Safe Workflow

Run these four steps before trusting filtered or aggregated output.

### Step 1 — Inspect Missing Values First

Start by checking where missing values appear and how many there are.

Example:

```python
print(df.isna().sum())
```

If needed, inspect rows that contain any missing values.

```python
print(df[df.isna().any(axis=1)].head())
```

This tells you which columns are affected before you filter or aggregate.

### Step 2 — Choose a Simple Strategy Per Column

Use one of these basic strategies for each important column.

#### Option A — Drop Rows with Missing Values

Use `dropna()` when rows without a value should be excluded from the analysis.

```python
df = df.dropna(subset=["salary"])
```

You can also drop rows that are completely empty or rows with any missing value.

```python
df = df.dropna(how="all")
df = df.dropna(how="any")
```

`how="all"` removes fully empty rows. `how="any"` is much stricter and removes rows if even one column is missing.

#### Option B — Fill Missing Values

Use `fillna()` when you want to keep the row and replace the missing value with a default.

```python
df["score"] = df["score"].fillna(0)
df["department"] = df["department"].fillna("Unknown")
```

Be careful with `fillna(0)`. It changes the values used by later aggregates.

### Step 3 — Compute Aggregates with Pandas Defaults

Pandas aggregate functions usually skip `NaN` automatically.

Examples:

```python
df["score"].mean()
df["score"].sum()
df["score"].count()
len(df)
```

Important distinction:

- `df["col"].count()` counts only non-null values
- `len(df)` counts all rows

That means `count()` should be less than or equal to `len(df)` whenever the column contains missing values.

For filtering, use `isna()` and `notna()` instead of direct equality checks.

```python
missing_scores = df[df["score"].isna()]
known_scores = df[df["score"].notna()]
```

### Step 4 — Verify the Result

After filtering or aggregating, run a simple sanity check.

Examples:

```python
assert df["score"].count() <= len(df)
print(df["score"].mean())
print(df["score"].sum())
```

If grouped results are involved, compare group counts against the overall non-null count.

```python
group_counts = df.groupby("department")["score"].count()
print(group_counts.sum(), df["score"].count())
```

The final numbers should be plausible given the number of missing rows.

## Basic Implementation Pattern

```python
def null_safe_summary(df, column):
    print(df.isna().sum())

    clean = df.dropna(subset=[column])

    print(f"total_rows={len(df)}")
    print(f"non_null_rows={clean[column].count()}")
    print(f"mean={clean[column].mean()}")
    print(f"sum={clean[column].sum()}")

    return clean
```

Example usage:

```python
df_clean = null_safe_summary(df, "score")
active_scores = df_clean[df_clean["status"].notna()]
```

## Practical Rules

### Inspect Before You Filter

Do not start dropping or filling values before you know which columns contain missing data.

### Use `subset=` for Important Columns

`dropna(subset=[...])` is usually safer than dropping rows based on all columns.

### Remember `count()` Is Not `len()`

If you mix these up, your aggregate interpretation will be wrong.

### Treat `fillna()` as a Real Data Change

Once you fill missing values, later filters and aggregates will use the replacement values.

## Common Pitfalls

- filtering rows before checking where `NaN` appears
- using `dropna(how="any")` too early and removing too much data
- filling values and then forgetting aggregates now include replacements
- confusing `count()` with total row count
- using direct comparisons instead of `isna()` and `notna()`

## When NOT to Use

- the data has no missing values
- the task is about schema inspection rather than NaN handling
- the main problem is type normalization instead of filtering or aggregation

## Quick Summary

```text
1. Check NaN counts with df.isna().sum()
2. Decide whether to drop or fill missing values
3. Use pandas aggregates, remembering they usually skip NaN
4. Compare count() against total rows
5. Verify the final result looks reasonable
```
