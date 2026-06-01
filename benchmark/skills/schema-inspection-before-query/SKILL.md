---
name: schema-inspection-before-query
description: Inspect CSV files and SQL tables before writing queries or data-processing code. Use this skill whenever the user asks for filtering, aggregation, joins, or analysis on tabular data and the schema must be checked first. Focus on quick practical inspection of columns, types, shape, sample rows, and join-key presence before any query is written.
metadata:
  environment: data-processing-structured-query
  skill_id: E3-LS1
  short-description: "Inspect CSV files and SQL tables before writing queries or data-processing code"
  version: "1.0"
---

# Schema Inspection Before Query

Use this workflow before writing pandas code, SQL queries, or join logic. The goal is simple: inspect the structure first so the query is based on real columns and types instead of assumptions.

Scope: quick schema inspection for CSV files and SQL tables.

## When to Use

Use this skill when:

- the user provides a CSV file, table, or database
- the task involves filtering, aggregation, joins, or grouping
- you are about to write pandas or SQL code against unfamiliar data

## Inspection Workflow

Run schema inspection before writing the query.

### Step 1 — Inspect CSV Structure

For CSV files, check shape, columns, dtypes, and sample rows.

Example:

```python
import pandas as pd

df = pd.read_csv("data.csv")

print(df.shape)
print(df.columns)
print(df.dtypes)
print(df.head())
```

What to look for:

- row and column count from `df.shape`
- actual field names from `df.columns`
- inferred types from `df.dtypes`
- sample values from `df.head()`

### Step 2 — Inspect SQL Table Structure

For SQL tables, inspect column names and types before querying.

SQLite:

```sql
PRAGMA table_info(table_name);
SELECT * FROM table_name LIMIT 5;
```

MySQL:

```sql
DESCRIBE table_name;
SELECT * FROM table_name LIMIT 5;
```

These commands show:

- which columns exist
- what types they use
- what sample rows look like

### Step 3 — Check for Obvious Problems

Before writing the query, confirm that:

- the expected columns actually exist
- the number of columns looks reasonable
- the data types are compatible with the planned query

Typical examples:

- a numeric field appears as `object` in pandas
- a query references a column that is not present
- a table has different columns than expected

### Step 4 — Check Join Keys Before Joining

Before writing a join, verify that the join key exists in both sources and appears usable.

Pandas example:

```python
print(df_left.columns)
print(df_right.columns)
print(df_left["id"].dtype)
print(df_right["id"].dtype)

left_keys = set(df_left["id"].dropna())
right_keys = set(df_right["id"].dropna())
print(len(left_keys & right_keys))
```

SQL example:

```sql
SELECT * FROM left_table LIMIT 5;
SELECT * FROM right_table LIMIT 5;
```

Before joining, confirm:

- the key column exists in both tables
- the key types look compatible
- there appears to be overlap in actual key values

## Practical Rules

### Always Inspect First

Do not write the query first and inspect later. Schema inspection is the first step, not a debugging step after failure.

### Use `df.dtypes` to Catch Wrong Types Early

`df.dtypes` quickly shows when a column is not being treated as the type you expect.

### Use Sample Rows Alongside Schema

Schema alone is not enough. Pair structure inspection with a small sample such as `df.head()` or `SELECT * ... LIMIT 5`.

## Common Pitfalls

- writing a query before checking whether the columns exist
- assuming a pandas column has the right dtype without checking `df.dtypes`
- joining two tables before verifying the join key in both
- inspecting only names and skipping sample rows

## When NOT to Use

- the schema is already known and stable in the current task
- the task does not involve tabular data or queries
- no query or data-processing step is being written

## Quick Summary

```text
1. For CSV: inspect head, dtypes, shape, and columns
2. For SQL: inspect schema and sample rows
3. Check for missing columns, wrong types, and column-count surprises
4. Before joins, verify the key exists in both sources and appears to overlap
```
