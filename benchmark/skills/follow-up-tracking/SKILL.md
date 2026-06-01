---
name: follow-up-tracking
description: Identify email threads that are overdue for a response by checking the direction of the last message, whether it contains a question or request, and how many business days have passed since it was received. Use this skill when the task is to scan one or more email threads, find items waiting on your reply, and produce an overdue follow-up list sorted by age. Focus on basic overdue detection based on last-message date and direction.
metadata:
  environment: communication-scheduling-operations
  skill_id: E6-LS3
  short-description: "Identify emails that need follow-up by scanning threads for overdue responses"
  version: "1.0"
---

# Follow-Up Tracking

Use this workflow when email threads need to be checked for overdue responses. The goal is to see who sent the last message, determine whether that message needs a reply from you, measure how long it has been waiting, and then output the overdue items from oldest to newest.

Scope: basic overdue detection based on last-message date and direction.

## When to Use

Use this skill when:

- the user wants to know which email threads still need a response
- the task is to find missed or overdue follow-ups
- multiple threads need a quick response audit
- the output should be a list of overdue items sorted by age

## Tracking Workflow

Follow these four steps for each thread.

### Step 1 — Check the Direction of the Last Message

Look at the most recent message in the thread and determine whether it was:

- sent by you
- received from someone else

If the last message was sent by you, the thread is not waiting on your reply.

If the last message was received from someone else, continue to the next step.

### Step 2 — Decide Whether the Thread Needs Follow-Up

Read the last received message and decide whether it requires action from you.

It needs follow-up if it contains:

- a question
- a request
- a document or item sent for your review
- a message clearly waiting for your response

It does not need follow-up if it is only:

- FYI
- a newsletter
- a general announcement
- a non-actionable informational message

This step is about separating actionable threads from informational ones.

### Step 3 — Check Whether It Is Overdue

For a thread that needs follow-up, check the date of the last received message.

If more than 3 business days have passed with no response from you, flag it as overdue.

Use a simple business-day rule:

- Monday to Friday count as business days
- weekends do not

Example:

```text
Received on Monday -> overdue after more than 3 business days without reply
```

### Step 4 — Output the Overdue Follow-Ups

Create a list of overdue threads sorted by age, oldest first.

For each thread, include:

- thread subject
- sender of the last message
- date received
- how old it is
- what the sender is waiting for

Example:

```text
1. "Q3 Budget Approval"
   From: Dana Chen
   Received: Oct 2
   Status: overdue
   Needs: budget sign-off

2. "Vendor Contract Review"
   From: legal@company.com
   Received: Oct 7
   Status: overdue
   Needs: feedback on contract draft
```

## Basic Implementation Pattern

```python
def needs_follow_up(last_message_from_me, last_message_text, business_days_waiting):
    if last_message_from_me:
        return False

    actionable = has_question(last_message_text) or has_request(last_message_text)
    overdue = business_days_waiting > 3

    return actionable and overdue
```

## Practical Rules

### Start with the Last Message

The most recent message determines whether the thread is currently waiting on you.

### Separate Action from FYI

A thread should only be flagged when the last received message actually expects a response.

### Use the 3-Business-Day Threshold Consistently

Apply the same overdue rule across threads so the output is predictable.

### Check If You Already Replied Elsewhere

If the matter was already answered in a different thread, do not treat the original thread as still waiting.

### Sort Oldest First

The oldest overdue items should appear at the top of the final list.

## Common Pitfalls

- flagging threads where your own message was the last reply
- treating informational emails as if they need action
- forgetting to use business days instead of calendar days
- ignoring whether a reply may already have been sent elsewhere
- returning overdue items in no clear order

## When NOT to Use

- the task is to draft a reply rather than find overdue threads
- the messages are not organized enough to identify thread direction
- the user wants a general inbox summary instead of follow-up tracking

## Quick Summary

```text
1. Check whether the last message was sent or received
2. If received, decide whether it needs a response
3. If it has waited more than 3 business days, mark it overdue
4. Output overdue follow-ups sorted oldest first
```
