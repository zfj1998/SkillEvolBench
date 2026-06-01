---
name: multi-source-merge-reconciliation
description: Merge flat data from 2-3 document sources into a single master document using exact key matching. Use this skill when records from multiple sources need to be combined by a shared identifier, duplicate entities need to be unified, conflicting field values need to be flagged, and a source-priority rule should decide which value is kept in the merged output. Focus on exact-key matching across 2-3 sources with flat data structures.
metadata:
  environment: document-parsing-extraction-transformation
  skill_id: E4-LS5
  short-description: "Merge flat data from 2-3 sources into a single master document"
  version: "1.0"
---

# Multi-Source Merge Reconciliation

Use this workflow when 2-3 flat document sources need to be merged into one master output. The goal is to match records by one exact identifier, collect all fields for each entity, flag conflicting values, and produce both a merged result and a conflict list.

Scope: exact-key matching across 2-3 sources with flat data structures.

## When to Use

Use this skill when:

- two or three sources contain records for the same entities
- the same entity appears in multiple files under the same exact key
- the task is to build one master document from several flat sources
- conflicts should be flagged instead of silently ignored

## Merge Workflow

Follow these five steps.

### Step 1 — Load All Sources

Read each source and note what records and fields it contains.

Example:

```text
Source A fields: id, name, department, salary
Source B fields: id, name, phone
Source C fields: id, name, department, title
```

At this stage, identify:

- which fields are shared across sources
- which fields appear in only one source

### Step 2 — Identify the Common Key

Choose the exact field used to identify the same entity across all sources.

Examples:

- `id`
- `email`
- `employee_number`

This key should:

- exist in every source used for the merge
- identify one entity per record
- match exactly across sources

If the merge key is `email`, then `alice@example.com` should match only the exact same key in another source.

### Step 3 — Collect Data for Each Unique Entity

Build a combined view for each unique key.

Example:

```text
Entity 10042
- Source A: name=Jane Doe, department=Engineering, salary=95000
- Source B: name=Jane Doe, phone=555-0100
- Source C: name=Jane Doe, title=Senior Engineer
```

For each entity, gather:

- the fields provided by each source
- the source names associated with those fields

### Step 4 — Resolve Conflicts with Source Priority

If two sources give different values for the same field, treat that as a conflict.

Example:

```text
Entity 10042
Field: department
Source A: Engineering
Source C: Product Engineering
```

Define a source priority order before choosing a resolved value.

Example:

```text
official records > self-reported data
```

Then:

- log the conflict
- choose the value from the higher-priority source
- keep the decision visible in the conflict report

Do not silently pick one conflicting value without recording it.

### Step 5 — Produce the Master Document and Conflict List

Output two results.

#### Output A — Master Document

One merged record per unique entity.

Example:

```text
id | name      | department  | salary | phone     | title
10042 | Jane Doe | Engineering | 95000  | 555-0100 | Senior Engineer
```

#### Output B — Conflict List

List every conflict found during the merge.

Example:

```text
Entity: 10042
Field: department
Source A: Engineering
Source C: Product Engineering
Resolved to: Engineering
Reason: Source A has higher priority
```

If no conflicts are found, still say that explicitly.

## Basic Implementation Pattern

```python
def merge_records(grouped_records, source_priority):
    merged = {}
    conflicts = []

    for entity_key, records in grouped_records.items():
        merged_row = {}

        for field in all_fields(records):
            values = collect_field_values(records, field)

            if len(values) == 1:
                merged_row[field] = values[0]["value"]
            else:
                chosen = choose_by_priority(values, source_priority)
                merged_row[field] = chosen["value"]
                conflicts.append({
                    "entity_key": entity_key,
                    "field": field,
                    "values": values,
                    "resolved_to": chosen["value"],
                })

        merged[entity_key] = merged_row

    return merged, conflicts
```

## Practical Rules

### Define the Merge Key First

Do not start combining rows until the shared exact key is clear.

### Use Exact Matches Only

This workflow assumes the same entity is identified by the same exact key value across sources.

### Set Source Priority Up Front

Conflict resolution is simpler and more consistent when the priority rule is defined before merging.

### Keep Conflicts Visible

Always output a conflict list instead of silently resolving disagreements.

### Produce One Master Record Per Unique Key

The final merged result should have one row or object per unique entity.

## Common Pitfalls

- starting the merge before choosing a shared key
- mixing records that do not share the same exact identifier
- silently overwriting conflicting field values
- forgetting to define source priority before reconciliation
- returning only the merged output without a conflict report

## When NOT to Use

- the sources do not share one clear exact key
- the task needs more advanced record matching than direct key equality
- the data structure is not flat enough for a simple field-by-field merge

## Quick Summary

```text
1. Load 2-3 sources
2. Identify the shared exact key
3. Collect all fields for each unique entity
4. Flag conflicting values and resolve them by source priority
5. Output the merged master document and the conflict list
```
