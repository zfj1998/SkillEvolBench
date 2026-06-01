---
name: evidence-grounded-comparison
description: Compare 3-5 options using evidence found in provided source documents. Use this skill when the task is to define comparison dimensions, search source material for evidence on each option, build a comparison matrix with source citations, identify which option is strongest on each dimension, and write a summary recommendation based on the completed matrix. Focus on evidence-based comparison tables built from provided documents.
metadata:
  environment: research-information-synthesis
  skill_id: E5-LS2
  short-description: "Compare multiple options using evidence from source documents"
  version: "1.0"
---

# Evidence-Grounded Comparison

Use this workflow when 3-5 options need to be compared using source documents rather than impressions. The goal is to define clear comparison dimensions, collect evidence for each option, build a matrix with citations, and then recommend an option based on the completed comparison.

Scope: evidence-based comparison matrices from provided source documents.

## When to Use

Use this skill when:

- several options need to be compared side by side
- the user wants an evidence-backed table or matrix
- the comparison should cite specific source support for each claim
- the final output should include both a matrix and a recommendation

## Comparison Workflow

Follow these five steps.

### Step 1 — Define the Comparison Dimensions

Start by choosing the dimensions that matter for the comparison.

Examples:

- price
- performance
- features
- support

Choose dimensions that:

- are relevant to all or most options
- are discussed in the provided sources
- can be compared clearly across the options

List them explicitly before collecting evidence.

Example:

```text
Comparison dimensions:
1. Price
2. Performance
3. Feature set
4. Support
```

### Step 2 — Search the Sources for Evidence

For each option and each dimension, search the sources for supporting evidence.

Look for:

- specific numbers
- direct statements
- concrete feature descriptions

Examples:

- `$49/month`
- `99.9% uptime`
- `includes 24/7 phone support`

Capture the evidence together with its source.

Example:

```text
Option: Vendor A
Dimension: Price
Evidence: $49/month
Source: Pricing Guide, page 2
```

If no evidence is available for a cell, record that explicitly rather than guessing.

### Step 3 — Build the Comparison Matrix

Put the evidence into a matrix or table.

Example:

```text
| Dimension   | Option A               | Option B               | Option C               |
|-------------|------------------------|------------------------|------------------------|
| Price       | $49/mo [S1]            | $39/mo [S2]            | No data                |
| Performance | 50ms [S1]              | 80ms [S2]              | 45ms [S3]              |
| Support     | Email only [S1]        | 24/7 phone [S2]        | Chat + email [S3]      |
```

Each cell should contain:

- the evidence itself
- a source citation

Use specific numbers and concrete quoted claims when available instead of vague wording.

### Step 4 — Identify the Strongest Option on Each Dimension

After the matrix is complete, determine which option appears strongest for each row.

Examples:

- lowest price wins on price
- highest performance number may win if larger is better
- strongest feature set may win on features

Write a short note explaining why that option is strongest on the given dimension.

Example:

```text
Price -> Option B
Reason: lowest listed monthly cost at $39/month
```

If a row is missing important evidence for one or more options, note that the comparison is incomplete for that dimension.

### Step 5 — Write a Summary Recommendation

Finish with a short recommendation based on the overall matrix.

The recommendation should:

- refer back to the evidence in the table
- note which option is strongest across the comparison
- mention any important missing cells that limit certainty

Keep the recommendation grounded in the filled matrix rather than adding new criteria that were not compared.

## Basic Implementation Pattern

```python
def comparison_matrix(options, dimensions, evidence_lookup):
    matrix = {}

    for dimension in dimensions:
        matrix[dimension] = {}
        for option in options:
            matrix[dimension][option] = evidence_lookup(option, dimension)

    return matrix
```

## Practical Rules

### Use Tables for Clear Comparison

A matrix makes it easier to compare multiple options across the same dimensions.

### Cite Specific Evidence

Specific numbers and direct source-backed statements are stronger than general descriptions.

### Keep Dimensions Consistent Across Options

Each option should be evaluated on the same set of dimensions whenever the data exists.

### Mark Missing Data Explicitly

If a cell has no support in the provided sources, say so directly.

### Base the Recommendation on the Matrix

The summary recommendation should follow from the completed evidence table, not from unsupported preferences.

## Common Pitfalls

- comparing options without first defining shared dimensions
- filling cells with vague claims instead of source-backed evidence
- forgetting to cite where each data point came from
- leaving missing cells blank instead of marking them as missing
- recommending an option for reasons not shown in the matrix

## When NOT to Use

- the task is to summarize one option rather than compare several
- there are not enough sources to support a multi-option comparison
- the user wants a free-form opinion instead of an evidence-backed matrix

## Quick Summary

```text
1. Define the comparison dimensions
2. Search the sources for evidence on each option and dimension
3. Fill a comparison matrix with evidence and citations
4. Identify the strongest option on each dimension
5. Write a summary recommendation based on the matrix
```
