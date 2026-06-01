---
name: inbox-triage-prioritization
description: Classify and prioritize incoming emails using simple category labels and explicit urgency markers. Use this skill when the task is to scan a batch of emails, assign each one to a fixed category, detect clear urgency keywords in the subject or opening sentences, and output a sorted list with High priority first, then Medium, then Low. Focus on keyword-based classification and explicit urgency markers.
metadata:
  environment: communication-scheduling-operations
  skill_id: E6-LS1
  short-description: "Classify and prioritize incoming emails into categories and urgency levels"
  version: "1.0"
---

# Inbox Triage Prioritization

Use this workflow when a batch of emails needs to be sorted quickly. The goal is to read each subject line and opening sentences, assign one of four fixed categories, detect any explicit urgency markers, and produce a priority-ordered output list.

Scope: keyword-based email classification with explicit urgency-marker priority assignment.

## When to Use

Use this skill when:

- a user wants help sorting a batch of emails
- the task is to decide what should be handled first
- emails need category labels and simple priority levels
- the output should be a sorted list of messages by priority

## Triage Workflow

Follow these four steps for each email.

### Step 1 — Read the Subject and Opening Sentences

For each email, read:

- the subject line
- the first few sentences of the body

This is enough for a quick classification pass.

Look for:

- category keywords
- sender context
- explicit urgency markers

Do not do a deep read at this stage.

### Step 2 — Assign One of Four Categories

Classify each email into exactly one category.

#### Customer Request

Use this when an external customer is asking for something.

Common signals:

- `request`
- `help`
- `question`
- `support`
- account or order references

#### Internal Task

Use this when a colleague is assigning work or asking for action.

Common signals:

- `please review`
- `action needed`
- `task`
- `your input needed`
- `can you`

#### FYI / Newsletter

Use this when the message is informational and does not require action.

Common signals:

- `FYI`
- `newsletter`
- `digest`
- `announcement`
- `update`
- `no action needed`

#### Technical Issue

Use this when the message is a bug report or system alert.

Common signals:

- `bug`
- `error`
- `alert`
- `incident`
- `outage`
- `failure`

### Step 3 — Assign Priority from Explicit Urgency Markers

Use only explicit urgency markers to determine priority.

#### High

Assign `High` if the subject or opening sentences contain markers such as:

- `[URGENT]`
- `ASAP`
- `high priority`
- `critical`
- `immediately`

#### Medium

Assign `Medium` if the email requires action but has no explicit urgency marker.

This usually applies to:

- Customer Request
- Internal Task
- Technical Issue

#### Low

Assign `Low` if the message is informational or non-actionable.

This usually applies to:

- FYI / Newsletter

### Step 4 — Output a Sorted List

Sort the results in this order:

1. High
2. Medium
3. Low

For each email, include:

- priority
- category
- subject
- sender

Example:

```text
HIGH
1. [Technical Issue] "[URGENT] API outage"
   From: alerts@company.com

MEDIUM
2. [Internal Task] "Please review Q3 budget"
   From: dana@company.com

LOW
3. [FYI / Newsletter] "Weekly company digest"
   From: newsletter@company.com
```

## Basic Implementation Pattern

```python
def classify_email(subject, opening):
    text = f"{subject} {opening}".lower()

    if any(k in text for k in ["bug", "error", "alert", "outage", "incident"]):
        category = "Technical Issue"
    elif any(k in text for k in ["request", "help", "support", "question"]):
        category = "Customer Request"
    elif any(k in text for k in ["please review", "action needed", "task", "your input needed"]):
        category = "Internal Task"
    else:
        category = "FYI / Newsletter"

    if any(k in text for k in ["[urgent]", "asap", "high priority", "critical", "immediately"]):
        priority = "High"
    elif category in {"Customer Request", "Internal Task", "Technical Issue"}:
        priority = "Medium"
    else:
        priority = "Low"

    return category, priority
```

## Practical Rules

### Read Only What You Need for Triage

The subject and first few sentences are usually enough for a first-pass classification.

### Use the Fixed Category Set

Every email should go into one of the four defined categories.

### Use Explicit Markers for High Priority

Only visible urgency words or tags should trigger `High`.

### Keep the Output Sorted by Priority

The final list should show High first, then Medium, then Low.

### Make the Result Easy to Scan

A short list with subject, sender, category, and priority is usually enough for triage.

## Common Pitfalls

- reading the full email before doing a quick triage pass
- assigning more than one category to a single email
- using vague intuition instead of visible keywords
- marking something High without an explicit urgency marker
- returning an unsorted output list

## When NOT to Use

- the user wants a full email response rather than triage
- the task is about deep intent analysis instead of quick inbox sorting
- the messages are not email-like enough for subject/opening-based classification

## Quick Summary

```text
1. Read each subject line and first few sentences
2. Assign one of four categories
3. Use explicit urgency markers to set High, Medium, or Low
4. Output a list sorted High first, then Medium, then Low
```
