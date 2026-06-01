---
name: contradiction-detection
description: Find direct factual contradictions between multiple information sources. Use this skill when two or more documents make claims about the same facts and the task is to extract those claims, group them by topic, compare the stated values, and report any contradictions with their sources. Focus on direct factual contradictions such as different numbers, dates, names, or statistics for the same fact.
metadata:
  environment: research-information-synthesis
  skill_id: E5-LS5
  short-description: "Find factual contradictions between multiple information sources"
  version: "1.0"
---

# Contradiction Detection

Use this workflow when multiple documents need to be checked for direct factual disagreement. The goal is to extract comparable claims, group them by topic, detect different stated values for the same fact, and report the contradiction clearly.

Scope: direct factual contradictions involving different numbers, dates, names, or statistics.

## When to Use

Use this skill when:

- several sources discuss the same facts
- the user wants to know whether the documents agree
- the task is to find conflicting reported values
- the output should include both the contradiction and the source of each value

## Detection Workflow

Follow these five steps.

### Step 1 — Extract Key Factual Claims

Read each source and pull out the concrete claims that can be compared across documents.

Focus on:

- numbers
- dates
- names
- statistics

Examples:

- `Q3 revenue was $4.2M`
- `The deadline is March 15`
- `The CEO is Jane Doe`
- `The survey found a 12% increase`

For each extracted claim, keep both the value and the source.

Example:

```text
Claim: Q3 revenue was $4.2M
Source: Annual Report, page 12
```

### Step 2 — Group Claims by Topic

Group claims that refer to the same fact into one comparison set.

Examples of topics:

- Q3 revenue
- project deadline
- employee headcount
- CEO name

Example grouping:

```text
Topic: Q3 revenue
- Source A: $4.2M
- Source B: $3.8M
- Source C: $4.2M
```

If a fact appears in only one source, it cannot form a contradiction by itself.

### Step 3 — Compare the Claims Within Each Group

Compare the values inside each topic group.

If the values are different, flag a contradiction.

Examples:

- `$4.2M` vs `$3.8M`
- `March 15` vs `March 22`
- `Jane Doe` vs `John Smith`
- `12%` vs `15%`

This skill focuses on direct stated-value comparison.

### Step 4 — Report Each Contradiction Clearly

For every contradiction, report:

- the topic
- the conflicting values
- the source for each value

Example:

```text
Contradiction: Q3 revenue
Source A: $4.2M (Annual Report, page 12)
Source B: $3.8M (Board Memo, page 3)
```

If three or more sources are involved, show which ones agree and which one differs.

Example:

```text
Contradiction: employee headcount
Source A: 340
Source B: 312
Source C: 340
Note: Sources A and C agree; Source B differs.
```

### Step 5 — Suggest Which Source May Be More Reliable

If possible, add a short note on which source may be more reliable.

Use:

- authority
- recency

Examples:

- official report over informal memo
- published final report over earlier draft
- newer corrected source over older source

If there is no clear basis for choosing, say that directly.

## Comparison Table Pattern

A table often makes contradictions easier to spot.

Example:

```text
| Topic            | Source A | Source B | Source C | Status         |
|------------------|----------|----------|----------|----------------|
| Q3 revenue       | $4.2M    | $3.8M    | $4.2M    | contradiction  |
| Project deadline | Mar 15   | Mar 22   | —        | contradiction  |
| CEO name         | Jane Doe | Jane Doe | Jane Doe | consistent     |
```

## Basic Implementation Pattern

```python
def detect_contradictions(grouped_claims):
    contradictions = []

    for topic, claims in grouped_claims.items():
        values = {claim["value"] for claim in claims}
        if len(values) > 1:
            contradictions.append({
                "topic": topic,
                "claims": claims,
            })

    return contradictions
```

## Practical Rules

### Start with Concrete Facts

Numbers, dates, names, and statistics are the easiest claims to compare reliably.

### Group Before Comparing

Do not compare raw claims one by one without first grouping them by the fact they discuss.

### Use a Table for Visibility

A comparison table makes direct contradictions easier to scan.

### Report Sources Alongside Values

Each conflicting value should stay attached to its source.

### Keep Reliability Notes Short

If you suggest a more reliable source, explain the basis briefly using authority or recency.

## Common Pitfalls

- extracting vague claims that cannot be compared directly
- comparing claims before grouping them by topic
- reporting different values without naming their sources
- treating a single-source fact as a contradiction
- flagging a contradiction but giving no reliability guidance when a clear basis exists

## When NOT to Use

- the task is to summarize the sources instead of comparing them
- the documents do not contain comparable factual claims
- the user wants a broader synthesis rather than contradiction finding

## Quick Summary

```text
1. Extract key factual claims from each source
2. Group claims by topic
3. Compare values within each group
4. Report contradictions with the conflicting values and sources
5. Suggest the more reliable source when authority or recency helps
```
