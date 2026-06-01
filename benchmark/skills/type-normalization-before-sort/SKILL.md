---
name: type-normalization-before-sort
description: Normalize inconsistent pandas column types before sorting or comparing values. Use this skill when a dataframe column mixes date formats, stores numbers as strings, or represents booleans in multiple textual forms and must be standardized before order-dependent operations. Focus on date, numeric, and boolean normalization in pandas DataFrames.
metadata:
  environment: data-processing-structured-query
  skill_id: E3-LS2
  short-description: "Normalize inconsistent pandas column types before sorting or comparing values"
  version: "1.0"
---

# Type Normalization Before Sort

Use this workflow when a pandas column cannot be sorted or compared correctly because its values are stored in inconsistent formats. The goal is to convert the entire column to one stable type before any order-dependent operation.

Scope: date, numeric, and boolean normalization in pandas.

## When to Use

Use this skill when:

- dates appear in multiple textual formats
- numeric values are stored as strings
- boolean values are represented in several ways
- sorting or comparison gives obviously wrong results because the column is still `object`

## Normalization Workflow

Follow these four steps for the target column.

### Step 1 — Inspect the Column Values

Check a small sample and the inferred dtype before writing conversion logic.

Example:

```python
print(df["date"].dtype)
print(df["date"].head(10))
print(df["date"].unique()[:10])
```

The purpose of inspection is to see which format variations exist before normalizing them.

### Step 2 — Write or Choose the Parsing Logic

Pick the conversion method that matches the column type:

- mixed dates -> `pd.to_datetime(...)`
- numeric strings -> `pd.to_numeric(...)`
- boolean variants -> explicit mapping function

If one built-in conversion can handle the column safely, prefer it over a custom parser.

### Step 3 — Apply the Conversion to the Whole Column

Convert the full column, not only a sample.

Examples:

```python
df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df["active"] = df["active"].apply(to_bool)
```

After conversion, use the normalized column for sorting or comparison.

### Step 4 — Verify the Result

Confirm that normalization actually worked.

Check:

- `df.dtypes`
- a small sample of converted values
- the sorted output

Example:

```python
print(df.dtypes)
print(df["date"].head())
print(df.sort_values("date").head())
```

Do not assume conversion succeeded just because the code ran.

## Scenario 1 — Mixed Date Formats

When a date column contains multiple textual formats, convert it to a datetime dtype before sorting.

Example values:

- `2024-01-15`
- `01/15/2024`
- `Jan 15, 2024`

Recommended conversion:

```python
df["date"] = pd.to_datetime(
    df["date"],
    format="mixed",
    errors="coerce",
)
```

If the dates are timezone-naive and the source does not specify a timezone, assume UTC after conversion:

```python
df["date"] = df["date"].dt.tz_localize("UTC")
```

Then sort:

```python
df = df.sort_values("date")
```

## Scenario 2 — String to Numeric

When numeric values are stored as strings, convert them before any comparison or sort.

Example values:

- `"100"`
- `"200"`
- `"9"`

Recommended conversion:

```python
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
```

Then verify:

```python
print(df["amount"].dtype)
print(df.sort_values("amount").head())
```

If the column should behave like integers after conversion, a nullable integer dtype can be useful:

```python
df["amount"] = df["amount"].astype("Int64")
```

## Scenario 3 — Boolean Normalization

When boolean values appear in multiple textual or numeric forms, map them to a standard boolean representation.

Common variants:

- `"true"` / `"false"`
- `"yes"` / `"no"`
- `"1"` / `"0"`

Example mapping:

```python
def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"true", "yes", "1"}:
            return True
        if value in {"false", "no", "0"}:
            return False
    if value in {1, 0}:
        return bool(value)
    return None

df["active"] = df["active"].apply(to_bool)
```

Then verify:

```python
print(df["active"].value_counts(dropna=False))
```

## Practical Rules

### Use Built-In Converters First

Prefer:

- `pd.to_datetime(..., format="mixed")`
- `pd.to_numeric(..., errors="coerce")`

They are usually simpler and more reliable than hand-written parsers.

### Normalize Before Sorting

Do not sort first and try to fix the output later. Type normalization is the prerequisite step.

### Spot-Check After Conversion

After normalization, inspect both the dtype and a few sorted rows to make sure the ordering now matches the intended type.

## Common Pitfalls

- sorting a date column while it is still string-like
- comparing numeric text lexicographically instead of numerically
- applying conversion to only part of the column
- failing to re-check `df.dtypes` after normalization
- trusting the conversion without spot-checking the sorted output

## When NOT to Use

- the column is already a clean, correct dtype
- the task does not depend on sorting, comparison, or order-sensitive operations
- the problem is schema discovery rather than type normalization

## Quick Summary

```text
1. Inspect the column values and dtype
2. Choose the parser or converter for that column
3. Apply it to the whole column
4. Verify with df.dtypes and spot-checking
5. Only then sort or compare
```
