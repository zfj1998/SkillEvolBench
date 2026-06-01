---
name: multi-source-search-filter
description: Search and filter the most relevant documents from a collection of 10-20 sources on a given topic. Use this skill when the task is to quickly scan a set of articles, papers, reports, or similar documents, score them for topical relevance, select the top 5 candidates, and rank those selected sources from most to least relevant. Focus on relevance-based selection using keyword matching, topic fit, specific data/examples, and source credibility.
metadata:
  environment: research-information-synthesis
  skill_id: E5-LS1
  short-description: "Search and filter relevant sources from a large collection of documents"
  version: "1.0"
---

# Multi-Source Search Filter

Use this workflow when a user has 10-20 sources on a topic and needs the most relevant ones selected quickly. The goal is to do a fast first pass, score each document for relevance, choose the best 5, and then explain why those 5 matter.

Scope: relevance-based selection using keyword matching and credibility assessment.

## When to Use

Use this skill when:

- a reading list or source set is too large to review in full
- the task is to narrow 10-20 documents down to the best few
- the user wants the most relevant sources for a target topic
- the output should include ranked selections and short relevance summaries

## Selection Workflow

Follow these five steps.

### Step 1 — Scan Titles and First Paragraphs

For each document, read:

- the title
- the first paragraph, abstract, or opening section

This is a quick relevance pass, not a full read.

Look for:

- direct keyword overlap with the target topic
- closely related terms or subtopics
- signs that the document will discuss the topic in substance

Example:

```text
Target topic: employee retention strategies
Title: Reducing Turnover Through Better Onboarding
Opening: discusses onboarding outcomes and retention impact
Initial judgment: relevant
```

### Step 2 — Score Each Document from 1 to 5

Assign a relevance score to each document.

Suggested scale:

- `5` = directly focused on the target topic and clearly useful
- `4` = strongly relevant but slightly narrower or broader than the topic
- `3` = partially relevant or useful as supporting context
- `2` = only loosely related
- `1` = not meaningfully relevant

Use these signals while scoring:

- keyword and topic match
- whether the document contains specific data or concrete examples
- whether the source is more or less credible

Credibility examples:

- academic journals
- established research reports
- professional publications
- blogs or informal posts

Example:

```text
Document: "Reducing Turnover Through Better Onboarding"
Topic match: strong
Specific examples: yes
Source credibility: high
Score: 5
```

### Step 3 — Select the Top 5 Documents

Sort the documents by score and keep the top 5.

If several documents tie, prefer:

- the one with stronger direct topic fit
- the one with more concrete data or examples
- the one from the more credible source

If fewer than 5 documents are meaningfully relevant, return fewer than 5 rather than padding the list with weak matches.

### Step 4 — Read the Selected Documents Fully

For each selected document, read the full text and write a short 2-sentence summary.

The summary should explain:

- what the document is about
- why it is relevant to the target topic

Example:

```text
This article examines how structured onboarding affects first-year employee retention.
It is relevant because it gives a concrete example of one retention strategy and the outcomes associated with it.
```

### Step 5 — Rank the 5 Selected Documents

Present the selected documents from most to least relevant.

For each ranked source, include:

- title
- source
- score
- 2-sentence relevance summary

Also show how many documents were reviewed and how many were selected.

## Basic Implementation Pattern

```python
def score_document(title, opening, topic):
    score = 1

    if topic.lower() in title.lower() or topic.lower() in opening.lower():
        score += 2

    if has_specific_examples(opening):
        score += 1

    if high_credibility_source(title):
        score += 1

    return min(score, 5)
```

## Practical Rules

### Use Keyword Matching as the First Filter

The initial scan should quickly separate obviously relevant documents from weak matches.

### Prefer Specific Data and Examples

Documents with concrete examples are usually more useful than very broad overviews.

### Factor in Source Credibility

A highly relevant document from a strong source should usually outrank a similar document from a weaker source.

### Read Only the Finalists in Full

Do not fully read all 10-20 documents at the start. Save the deeper read for the top selections.

### Rank the Final Set Explicitly

The user should see not just which documents survived filtering, but also which of the selected ones are strongest.

## Common Pitfalls

- reading every document fully before doing a quick relevance pass
- scoring without a consistent 1-5 rubric
- picking general overviews over stronger topic-specific sources
- ignoring source credibility when two documents seem similarly relevant
- selecting weak documents just to force the list to contain five items

## When NOT to Use

- the task is to synthesize all sources rather than filter them
- there are too few documents to justify a ranking pass
- the user already knows which sources should be included

## Quick Summary

```text
1. Scan each title and first paragraph
2. Score each document from 1 to 5
3. Select the top 5 highest-scoring documents
4. Read those 5 fully and write 2-sentence relevance summaries
5. Rank the selected documents from most to least relevant
```
