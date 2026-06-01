---
name: meeting-scheduling-constraints
description: Find a common meeting time for 2-3 participants across 2 time zones using fixed UTC offsets. Use this skill when the task is to list participants and time zones, convert business-hour availability into UTC, find the overlapping UTC range, convert that overlap back into local times, and suggest a specific meeting time within the overlap. Focus on scheduling with fixed UTC offsets and standard business hours.
metadata:
  environment: communication-scheduling-operations
  skill_id: E6-LS4
  short-description: "Find a common meeting time for participants across different time zones"
  version: "1.0"
---

# Meeting Scheduling Constraints

Use this workflow when a meeting needs to be scheduled across two time zones. The goal is to convert each participant's working hours into UTC, find the shared overlap, convert it back to local time, and then choose one concrete meeting slot.

Scope: scheduling with 2-3 participants across 2 time zones using fixed UTC offsets.

## When to Use

Use this skill when:

- a user needs a meeting time that works across time zones
- the participants are in different cities or regions
- the task is to find overlap within business hours
- the output should include one recommended meeting time in each local zone

## Scheduling Workflow

Follow these five steps.

### Step 1 — List Participants and Time Zones

Start by listing:

- each participant
- their time zone
- their UTC offset

Example:

```text
Alice -> EST -> UTC-5
Bob -> CET -> UTC+1
```

If no availability is given, assume standard business hours:

- `09:00-17:00` local time

### Step 2 — Convert Each Availability Window to UTC

Convert each participant's local available hours into UTC.

Examples:

- EST = UTC-5
- CET = UTC+1
- JST = UTC+9

Example conversion:

```text
Alice: 09:00-17:00 EST -> 14:00-22:00 UTC
Bob:   09:00-17:00 CET -> 08:00-16:00 UTC
```

Use a fixed UTC offset table rather than time-zone rules.

### Step 3 — Find the Overlapping UTC Range

Compare all UTC ranges and find the overlap where everyone is available.

Rule:

- overlap start = latest start time
- overlap end = earliest end time

Example:

```text
Alice UTC: 14:00-22:00
Bob UTC:   08:00-16:00
Overlap:   14:00-16:00 UTC
```

If the overlap start is before the overlap end, you have a valid shared window.

### Step 4 — Convert the Overlap Back to Local Time

Take the overlap window and convert it back into each participant's local time.

Example:

```text
Overlap: 14:00-16:00 UTC

Alice (EST): 09:00-11:00
Bob (CET):   15:00-17:00
```

This makes it easy to confirm the shared slot is practical for each person.

### Step 5 — Suggest a Specific Meeting Time

Choose one meeting time inside the overlap.

Preferred rule:

- choose a mid-morning time in the majority time zone when possible

If there is no clear majority, choose a time near the middle of the overlap.

Example:

```text
Overlap: 14:00-16:00 UTC
Suggested time: 15:00 UTC

Alice: 10:00 EST
Bob:   16:00 CET
```

## Handling No Overlap

If there is no shared overlap inside normal business hours, suggest the least-bad option by choosing the time closest to the edges of both availability windows.

Example:

```text
No perfect overlap found.

Suggested least-bad option: 13:00 UTC
Alice: 08:00 EST
Bob:   18:00 CET
```

State clearly that the suggested time falls outside at least one normal business-hours window.

## UTC Offset Reference Pattern

Useful examples:

```text
EST = UTC-5
CET = UTC+1
JST = UTC+9
```

You can extend this table when needed for the participants involved.

## Basic Implementation Pattern

```python
def overlap_range(ranges):
    start = max(r[0] for r in ranges)
    end = min(r[1] for r in ranges)
    if start < end:
        return (start, end)
    return None
```

## Practical Rules

### Use UTC as the Shared Comparison Space

Do not compare local business hours directly across regions. Convert them to UTC first.

### Respect Standard Business Hours

Unless the user provides different windows, use `09:00-17:00` local time.

### Show the Overlap Before Choosing a Time

The user should be able to see the full shared window, not just the final recommendation.

### Convert the Final Suggestion Back to Local Time

A UTC-only answer is harder to use in practice.

### Be Explicit When There Is No Perfect Slot

If no true overlap exists, say so before proposing the least-bad option.

## Common Pitfalls

- mixing local times without converting to UTC first
- using the wrong sign for a UTC offset
- choosing a time before confirming the full overlap
- giving a UTC time without local equivalents
- failing to say when the suggested time falls outside normal business hours

## When NOT to Use

- the task is about calendar booking rather than time-slot finding
- the user already provides one confirmed meeting time
- the scheduling problem needs a richer process than fixed-offset overlap

## Quick Summary

```text
1. List participants and their UTC offsets
2. Convert local business hours to UTC
3. Find the overlapping UTC range
4. Convert that overlap back to local time
5. Suggest a meeting time inside the overlap, or the least-bad option if none exists
```
