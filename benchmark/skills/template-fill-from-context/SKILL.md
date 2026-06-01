---
name: template-fill-from-context
description: Fill a template document using information found in one or two context documents. Use this skill when a template contains blank fields or placeholders and the task is to locate matching information in surrounding context, insert it into the template, and return a completed version. Focus on straightforward fill-from-context work with one template, one or two context documents, simple field-name matching, and basic output review.
metadata:
  environment: document-parsing-extraction-transformation
  skill_id: E4-LS3
  short-description: "Populate document templates with data extracted from context files"
  version: "1.0"
---

# Template Fill from Context

Use this workflow when a template has empty fields and the needed values appear in one or two context documents. The goal is to identify every field that needs a value, find the matching information in context, fill the template in the expected format, and review the result for completeness.

Scope: straightforward fill-from-context with one template and one or two context documents.

## When to Use

Use this skill when:

- a form or template contains placeholders such as `[Full Name]` or `{{email}}`
- a context document contains the facts needed to complete the template
- the task is to transfer information from source text into a structured template
- the result should be a completed template plus any remaining `TODO` fields

## Fill Workflow

Follow these five steps.

### Step 1 — Read the Template and List Empty Fields

Start with the template and identify every field that still needs a value.

Common field patterns:

- `[Full Name]`
- `{{start_date}}`
- `Phone: _______`
- `Date of Birth:`

Write down the fields exactly as they appear so nothing is missed.

Example:

```text
Fields to fill:
- Full Name
- Date of Birth
- Email Address
- Phone Number
- Start Date
```

If a field implies a format, note it now. For example:

- dates may need ISO format such as `2024-01-15`
- numeric fields may need digits only

### Step 2 — Read the Context Documents

Read the context material and extract facts that might map to template fields.

Look for:

- labeled values such as `Name: John Smith`
- sentence-level facts such as `John Smith joined on January 15, 2024`
- small tables or lists that contain contact or profile details

At this stage, the goal is to gather candidate values before deciding which field they belong to.

### Step 3 — Match Template Fields to Context Information

For each template field, search the context for the matching fact.

Field names may differ slightly, so match by meaning as well as exact text.

Examples:

- `Full Name` in the template may match `Name` in the context
- `Phone Number` may match `Phone`, `Tel`, or `Contact Number`
- `Email Address` may match `Email`

Example mapping:

```text
Full Name -> Name: John Smith
Phone Number -> Tel: +1-555-0100
Start Date -> Joined on January 15, 2024
```

If a field is genuinely not present in the context, leave a visible marker such as `[TODO: not found in context]`.

### Step 4 — Fill the Template in the Correct Format

Insert the matched value into the template and normalize the format when needed.

Examples:

- `January 15, 2024` -> `2024-01-15`
- `Name: John Smith` -> `John Smith`
- `Amount: 2500` -> `2500`

Preserve the surrounding template structure while replacing only the empty fields.

### Step 5 — Review for Completeness and Accuracy

After filling the template, review the result.

Check:

- every field from Step 1 is now filled or marked with `TODO`
- inserted values match the intended field
- dates and numbers use the expected format
- no placeholder tokens remain by accident

## Basic Implementation Pattern

```python
def fill_template(template_fields, extracted_context):
    filled = {}

    for field in template_fields:
        value = extracted_context.get(field)
        if value is None:
            filled[field] = "[TODO: not found in context]"
        else:
            filled[field] = value

    return filled
```

Example matching dictionary:

```python
extracted_context = {
    "Full Name": "John Smith",
    "Email Address": "john@example.com",
    "Phone Number": "+1-555-0100",
    "Start Date": "2024-01-15",
}
```

## Practical Rules

### Read the Whole Template First

Do not fill fields one by one as you discover them. First build the full field list.

### Match by Meaning, Not Only Exact Labels

Template labels and context labels may use different wording for the same concept.

### Normalize Formats Before Inserting

Convert dates and numeric-looking values into the format the template expects.

### Keep Missing Fields Visible

If a value is not found, leave a `TODO` marker so the incomplete parts are easy to review later.

### Review the Final Filled Version

A successful fill is not just about inserting values. The finished template should also be complete and readable.

## Common Pitfalls

- skipping fields because the template was not scanned completely
- matching only exact labels and missing obvious synonyms
- inserting raw values without formatting them for the template
- forgetting to mark missing fields with a visible `TODO`
- leaving original placeholder tokens in the final document

## When NOT to Use

- the template requires more complex logic than direct field filling
- the task is about extracting a standalone JSON record rather than filling a template
- the document does not have a clear template-plus-context structure

## Quick Summary

```text
1. Read the template and list all empty fields
2. Read one or two context documents and extract candidate facts
3. Match each field to the relevant context value
4. Fill the template using the expected formats
5. Review the final template for completeness and remaining TODO markers
```
