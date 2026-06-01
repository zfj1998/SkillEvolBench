---
name: cross-format-migration
description: Convert flat documents from one format to another while preserving source content. Use this skill when the task is to migrate content such as Markdown, CSV, or simple key-value text into JSON, and the goal is to keep all body content represented in the target format. Focus on flat-format migration with explicit source-to-target mapping, parser-based conversion, and a final source-versus-target verification step.
metadata:
  environment: document-parsing-extraction-transformation
  skill_id: E4-LS2
  short-description: "Convert documents between formats while preserving all content"
  version: "1.0"
---

# Cross-Format Migration

Use this workflow when content needs to move from one simple document format into JSON without dropping information. The goal is to understand the source structure first, map each source element into the target schema, run the conversion, and then verify that the content is still present in the result.

Scope: content migration between flat formats.

## When to Use

Use this skill when:

- a Markdown document needs to become JSON
- a CSV file needs to become an array of JSON objects
- `Key: Value` text needs to become a JSON object
- the user asks to convert one flat text format into another structured form

## Conversion Workflow

Follow these five steps.

### Step 1 — Read the Source Format Carefully

Before converting, identify how the source format is organized.

Common patterns:

- Markdown: headings followed by paragraph text
- CSV: one header row and multiple data rows
- key-value text: one field per line in `Key: Value` form

Do not start converting until you know what the source elements are.

### Step 2 — Define the Target JSON Schema

Decide what the JSON output should look like before writing conversion logic.

Typical schemas:

- Markdown -> one JSON object
- CSV -> one JSON object per row, stored in an array
- key-value text -> one JSON object

Examples:

```json
{
  "status": "In Progress",
  "owner": "Jane Chen"
}
```

```json
[
  {"name": "Jane Chen", "department": "Engineering"},
  {"name": "Bob Torres", "department": "Sales"}
]
```

Use stable field names and decide them up front.

### Step 3 — Write the Source-to-Target Mapping

Explicitly map source elements to target fields.

Examples:

- Markdown heading `# Owner` -> JSON key `owner`
- CSV column `department` -> JSON key `department`
- text line `Start Date: 2024-01-15` -> JSON key `start_date`

This keeps the conversion auditable and makes verification easier later.

### Step 4 — Execute the Conversion

Use existing parsers whenever possible instead of writing custom parsers from scratch.

#### Markdown -> JSON

For a flat Markdown document, headings become keys and the paragraph content under each heading becomes the value.

```python
import re

def markdown_to_json(text):
    result = {}
    current_key = None
    buffer = []

    for line in text.splitlines():
        match = re.match(r"^#+\s+(.+)$", line)
        if match:
            if current_key is not None:
                result[current_key] = "\n".join(buffer).strip()
            current_key = match.group(1).strip().lower().replace(" ", "_")
            buffer = []
        else:
            buffer.append(line)

    if current_key is not None:
        result[current_key] = "\n".join(buffer).strip()

    return result
```

#### CSV -> JSON

Use the standard `csv` library so quoted fields, commas, and embedded newlines are handled correctly.

```python
import csv

def csv_to_json(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
```

#### Key-Value Text -> JSON

Split each line on the first colon only.

```python
def key_value_to_json(text):
    result = {}
    for line in text.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        result[key.strip().lower().replace(" ", "_")] = value.strip()
    return result
```

When writing JSON output, let the JSON serializer handle quotes, escaping, and newline characters.

### Step 5 — Verify Nothing Important Was Lost

After conversion, compare the source and target.

Basic checks:

- all expected source elements appear in the target
- row counts match for CSV conversions
- important values are still present and not truncated
- the converted output still reflects the original order when possible

Examples:

```python
print(len(result))
print(result)
```

```python
print(source_text)
print(target_json)
```

If the source contains three headings, three rows, or five key-value lines, the target should reflect those same elements.

## Basic Implementation Pattern

```python
def migrate_to_json(source, source_type):
    if source_type == "markdown":
        result = markdown_to_json(source)
    elif source_type == "csv":
        result = csv_to_json(source)
    elif source_type == "key_value":
        result = key_value_to_json(source)
    else:
        raise ValueError("Unsupported source type")

    return result
```

## Practical Rules

### Understand the Source Before Mapping

Conversion is easier and safer when you first identify the real source structure.

### Prefer Existing Parsers

Use `csv`, `json`, or a Markdown parser when possible instead of manual string splitting everywhere.

### Normalize Keys Consistently

Turn labels such as `Start Date` into stable keys such as `start_date`.

### Preserve Text Exactly When Possible

Do not silently rewrite paragraph text, quoted values, or embedded newlines during conversion.

### Verify the Target Against the Source

A conversion is not complete until you compare the output against the original source content.

## Common Pitfalls

- converting before understanding the source structure
- using manual CSV splitting instead of a parser
- dropping lines that do not match the expected pattern
- changing key names inconsistently across similar inputs
- skipping a source-versus-target verification pass

## When NOT to Use

- the source document needs a more advanced transformation than flat migration
- the target should preserve a complex structure rather than a simple JSON form
- the task is about extracting only a few fields instead of migrating full content

## Quick Summary

```text
1. Read the source format carefully
2. Define the target JSON schema
3. Map source elements to target fields
4. Execute the conversion with existing parsers
5. Compare source and target to confirm content was preserved
```
