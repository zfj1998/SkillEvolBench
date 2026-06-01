---
name: constrained-summarization
description: Generate summaries that must satisfy explicit constraints such as a word limit, required key points, and a requested presentation format. Use this skill when the task is to condense a long document into a shorter summary while staying within a stated word cap, ensuring required points are included, and checking the final draft against those constraints before returning it. Focus on word-limited summaries with required key point coverage.
metadata:
  environment: research-information-synthesis
  skill_id: E5-LS4
  short-description: "Generate summaries under specific constraints like word limits, required key points, and format requirements"
  version: "1.0"
---

# Constrained Summarization

Use this workflow when a long document needs to be summarized under clear limits. The goal is to identify the main points, apply the stated constraints, draft a summary that fits those constraints, and revise it until it passes all checks.

Scope: word-limited summaries with required key point coverage.

## When to Use

Use this skill when:

- the user specifies a word limit
- certain points must appear in the summary
- the summary has to follow a requested format
- the task is to shorten a document without dropping required content

## Summarization Workflow

Follow these five steps.

### Step 1 — Read the Full Document and Identify Main Points

Read the source document before drafting anything.

While reading, note:

- the main conclusions
- the most important supporting points
- any points that seem central to the document's message

At this stage, build a rough list of the candidate points the summary could include.

### Step 2 — Check the Constraints

Before writing, confirm the constraints that the summary must satisfy.

Common constraints:

- word limit
- required key points
- format requirements

Examples:

- `under 150 words`
- `must mention revenue, timeline, and risks`
- `single paragraph` or `bullet summary`

If the user provides required points, treat them as mandatory coverage targets.

### Step 3 — Draft a Summary That Covers the Required Points

Write a first draft that includes all required points while aiming to stay within the word limit.

When space is limited:

- start with the most important point
- use concise wording
- cut background detail before cutting key content

The first draft does not need to be perfect, but it should already try to satisfy the constraints.

### Step 4 — Review the Draft Against the Constraints

After drafting, check the summary against all stated requirements.

Review checklist:

- is the word count within the limit
- are all required points mentioned
- does the summary match the requested format

Example word count check:

```python
word_count = len(text.split())
```

Example checklist:

```text
Required points:
- revenue -> included
- timeline -> included
- risks -> missing
```

If any requirement fails, revise the draft before returning it.

### Step 5 — Revise Until the Summary Fits

If the summary is too long or misses a required point, revise it.

Useful revision moves:

- remove background context
- replace long phrases with shorter wording
- merge sentences when possible
- cut non-required detail

After revising, run the same checks again:

- word count
- required key point coverage
- format compliance

Repeat until the summary passes all constraints.

## Basic Implementation Pattern

```python
def constrained_summary_check(text, required_points, max_words):
    word_count = len(text.split())
    missing = [p for p in required_points if p not in text]

    return {
        "word_count": word_count,
        "within_limit": word_count <= max_words,
        "missing_points": missing,
    }
```

## Practical Rules

### Prioritize the Most Important Points

When space is tight, the most important content should survive first.

### Keep Required Points Non-Negotiable

If the user says a point must be included, revise other parts before dropping it.

### Use Concise Language

Shorter, clearer phrasing creates room for more required content.

### Check Constraints Explicitly

Do not assume the summary fits the word cap or covers every required point. Check it directly.

### Revise More Than Once If Needed

A constrained summary often needs one draft plus one or two tightening passes.

## Common Pitfalls

- drafting before confirming the real constraints
- spending too many words on background detail
- forgetting to include one of the required points
- returning a summary without checking the word count
- keeping the right content but ignoring the requested format

## When NOT to Use

- the task is to write an open-ended summary with no clear constraints
- the user wants a full synthesis instead of a compressed summary
- there is no need to optimize for space or required point coverage

## Quick Summary

```text
1. Read the full document and identify the main points
2. Check the word limit, required points, and format
3. Draft a summary that covers the required content
4. Review word count, point coverage, and format
5. Revise until all constraints are satisfied
```
