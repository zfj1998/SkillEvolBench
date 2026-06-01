---
name: structured-field-extraction
description: Extract structured data from semi-structured documents such as invoices, forms, and reports, then convert the extracted fields to JSON. Use this skill when a document contains label-value pairs, markdown-style tables, or section headers that organize fields into simple categories. Focus on flat key-value extraction from single-format documents, with basic field validation after extraction.
metadata:
  environment: document-parsing-extraction-transformation
  skill_id: E4-LS1
  short-description: "Extract structured data from semi-structured documents and convert it to JSON"
  version: "1.0"
---

# Structured Field Extraction

Use this workflow to extract fields from a semi-structured document and return them as JSON. The goal is to read the document structure first, choose the matching extraction pattern, and then validate the extracted fields before returning the result.

Scope: flat key-value extraction from single-format documents.

## When to Use

Use this skill when:

- a document contains fields like `Invoice Number: INV-001`
- a report groups fields under section headers
- a document contains a simple markdown-style table
- the user wants document content converted into JSON fields

## Extraction Workflow

Follow these four steps.

### Step 1 — Scan the Document Structure

Read the document first and identify its primary structure:

- label-value text
- tabular content
- section-based content

Look for signals such as:

- repeated `Label: Value` lines
- markdown table rows with `|`
- headers like `## Summary` or bold section labels

Choose the one pattern that best matches the document.

### Step 2 — Extract Fields by Pattern

Use the extraction technique that matches the document.

#### Pattern A — Label-Value Pairs

Use this when the document mainly contains lines such as:

```text
Invoice Number: INV-001
Date: Jan 15, 2024
Amount Due: $125.00
```

Regex is useful for splitting label and value:

```python
import re

match = re.match(r"^([^:]+):\s*(.+)$", line)
```

After matching:

- normalize the label into a JSON key
- keep the extracted value as text first
- normalize types afterward if needed

Useful regex targets:

- dates
- amounts
- IDs

#### Pattern B — Table Extraction

Use this when the document is mainly a table and should become an array of objects.

Example markdown table:

```markdown
| Item | Amount | Date |
|------|--------|------|
| A    | 10.50  | 2024-01-15 |
| B    | 20.00  | 2024-01-16 |
```

Extraction pattern:

```python
headers = ["item", "amount", "date"]
rows = [
    {"item": "A", "amount": "10.50", "date": "2024-01-15"},
    {"item": "B", "amount": "20.00", "date": "2024-01-16"},
]
```

Each row should map to one object using the header row as keys.

#### Pattern C — Section-Based Extraction

Use this when section headers split the document into simple categories.

Example:

```markdown
## Company Information
Name: Acme Corp
Date: 2024-01-15

## Contact
Email: info@acme.com
Phone: 555-0100
```

Use the section header as the category and extract the fields inside it.

```json
{
  "company_information": {
    "name": "Acme Corp",
    "date": "2024-01-15"
  },
  "contact": {
    "email": "info@acme.com",
    "phone": "555-0100"
  }
}
```

### Step 3 — Organize the Output as JSON

After extraction, organize the data into a JSON structure that matches the document pattern:

- one object for label-value extraction
- an array of objects for a table
- section-grouped objects for section-based extraction

Keep the output consistent and use stable field names.

### Step 4 — Validate Required Fields and Types

Before returning the result, check that required fields are present and that important values look valid.

Example checks:

```python
required_fields = ["invoice_number", "date"]
missing = [f for f in required_fields if f not in result]
print(missing)
```

Also verify obvious types after extraction:

- date fields should look like dates
- amount fields should look numeric
- IDs should remain stable strings when appropriate

If a document contains multiple date formats, normalize them after extraction into one standard format.

## Basic Implementation Pattern

```python
def extract_document(text):
    if "|" in text:
        result = extract_table(text)
    elif "## " in text:
        result = extract_sections(text)
    else:
        result = extract_label_value_pairs(text)

    validate_result(result)
    return result
```

## Practical Rules

### Scan Before Extracting

Do not start with regex immediately. First identify whether the document is mostly label-value, table-based, or section-based.

### Normalize Keys Consistently

Convert labels such as `Invoice Number` into stable JSON keys such as `invoice_number`.

### Extract First, Normalize Second

It is usually safer to capture the field text first, then normalize dates, amounts, or IDs afterward.

### Validate Before Returning JSON

A structured result is only useful if required fields exist and the important values look plausible.

## Common Pitfalls

- extracting fields without first checking the document structure
- mixing labels from different sections into one flat object by accident
- returning inconsistent key names across similar documents
- failing to check required fields before returning JSON
- skipping date normalization when the document uses multiple date formats

## When NOT to Use

- the task needs a more advanced parser than simple field extraction
- the document does not have one clear dominant structure
- the output is not meant to be a simple JSON extraction result

## Quick Summary

```text
1. Scan the document structure
2. Choose label-value, table, or section-based extraction
3. Convert the extracted fields into JSON
4. Validate required fields and basic value types
5. Normalize dates and keys before returning the result
```
