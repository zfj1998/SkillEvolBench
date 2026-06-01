---
name: thread-action-extraction
description: Extract explicit action items from formal business email threads. Use this skill when the task is to read an email conversation, identify direct requests, named assignments, and explicit sender commitments, and output structured action items with a task description, assignee, deadline, and source email. Focus on extracting explicit action items from professional email threads.
metadata:
  environment: communication-scheduling-operations
  skill_id: E6-LS5
  short-description: "Extract action items (tasks, to-dos, commitments, follow-ups) from email threads"
  version: "1.0"
---

# Thread Action Extraction

Use this workflow when an email thread needs to be turned into a clean list of action items. The goal is to read the thread, identify explicit tasks and commitments, extract the key fields for each item, and return a structured action list.

Scope: extracting explicit action items from formal business email threads.

## When to Use

Use this skill when:

- the user wants a task list from an email thread
- the thread contains requests, assignments, or commitments
- the result should show who needs to do what
- the output should include deadlines and source references when available

## Extraction Workflow

Follow these four steps.

### Step 1 — Read the Full Thread

Read the thread before extracting anything.

This matters because:

- a later reply may clarify or update a request
- more than one person may be assigned work in the same thread
- deadlines may appear in a different message than the task itself

The extraction should reflect the thread as a whole, not one isolated email.

### Step 2 — Identify Explicit Action Patterns

Extract action items only when they match one of these explicit patterns.

#### Pattern 1 — Direct Requests

The sender asks the recipient to do something.

Examples:

- `Please send the revised budget by Friday.`
- `Could you review the draft?`
- `Need to follow up with finance on this.`

Extract:

- action
- assignee = recipient
- deadline if present

#### Pattern 2 — Named Assignments

The sender clearly assigns a task to a named person.

Examples:

- `Jordan, can you coordinate with the vendor?`
- `Alex, please handle the final review.`

Extract:

- action
- assignee = named person
- deadline if present

#### Pattern 3 — Explicit Sender Commitments

The sender commits to doing something in explicit form.

Examples:

- `I will send the agenda by Wednesday.`
- `I'll circulate the notes tomorrow.`

Extract:

- action
- assignee = sender
- deadline if present

### Step 3 — Fill the Required Fields

For every extracted action item, record these fields:

- description
- assignee
- deadline
- source

Field guidance:

- `description`: short task summary
- `assignee`: recipient, named person, or sender based on the pattern
- `deadline`: exact phrasing if one is mentioned; otherwise `None specified`
- `source`: enough information to identify the email where the action came from

Example:

```text
Description: Send revised budget to finance
Assignee: Recipient
Deadline: Friday
Source: Email from Dana, Oct 8
```

### Step 4 — Output the Action List

Present the extracted items in a clear structured format.

Example:

```text
1. Send revised budget to finance
   Assignee: Alex
   Deadline: Friday
   Source: Email from Dana, Oct 8

2. Coordinate with vendor on new timeline
   Assignee: Jordan
   Deadline: None specified
   Source: Email from Dana, Oct 8
```

If no explicit action items are found, say so directly.

## Useful Action Signals

Look for clear action language such as:

- `please`
- `need to`
- `make sure`
- `follow up`
- `can you`
- `I will`

These signals usually indicate that a real task or commitment is being stated.

## Distinguishing Actions from Non-Actions

Not every sentence in a thread is an action item.

Usually extract:

- direct requests
- clear assignments
- explicit commitments

Usually do not extract:

- status updates
- purely informational statements
- opinions or commentary
- vague discussion with no concrete task

The key question is:

- does this sentence assign or commit to a specific task

## Handling Vague Deadlines

If the deadline wording is vague, record it as written rather than inventing a precise date.

Examples:

- `soon`
- `when you can`
- `ASAP`

If no deadline appears at all, record:

- `None specified`

## Basic Implementation Pattern

```python
def action_item(description, assignee, deadline, source):
    return {
        "description": description,
        "assignee": assignee,
        "deadline": deadline or "None specified",
        "source": source,
    }
```

## Practical Rules

### Read Before Extracting

Later messages can change how an earlier request should be understood.

### Extract Only Explicit Actions

This workflow is for clearly stated tasks and commitments, not implied work.

### Keep the Description Short

The task summary should be concise and easy to scan.

### Preserve the Deadline Wording

If a deadline is present, keep the wording close to the source text.

### Always Attach a Source

Every action item should say which email it came from.

## Common Pitfalls

- extracting general discussion as if it were a task
- missing the assignee when a named person is explicitly addressed
- inventing a deadline that the thread never states
- returning actions without noting the source email
- ignoring later thread context that clarifies an earlier request

## When NOT to Use

- the user wants a thread summary instead of a task list
- the messages are too informal for explicit action extraction
- the task is about later workflow management rather than action identification

## Quick Summary

```text
1. Read the full thread
2. Identify direct requests, named assignments, and explicit sender commitments
3. Extract description, assignee, deadline, and source
4. Output a structured action-item list
```
