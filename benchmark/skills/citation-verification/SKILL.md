---
name: citation-verification
description: Verify that citations in a document accurately represent their sources. Use this skill when a paper, review article, report, or essay makes claims about external sources and the task is to check whether those cited sources actually support the attributed statements. Focus on verifying that claims, quotes, and numerical assertions are supported by the cited source content.
metadata:
  environment: research-information-synthesis
  skill_id: E5-LS3
  short-description: "Check whether citations in a document accurately represent their sources"
  version: "1.0"
---

# Citation Verification

Use this workflow when a document makes claims about cited sources and those claims need to be checked against the original source material. The goal is to confirm whether each cited source actually supports what the document says about it.

Scope: verifying that cited sources support the claims made about them.

## When to Use

Use this skill when:

- a review article attributes findings to cited studies
- a report uses citations to support factual claims
- a document includes direct quotes that need checking
- the user wants a citation audit rather than a general summary

## Verification Workflow

Follow these five steps.

### Step 1 — Identify Claims That Cite Sources

Read the document and list each claim that explicitly attributes information to a source.

Examples:

- `According to Smith (2023), the rate increased by 20%.`
- `Jones (2022) argues that remote work improved retention.`
- `"The intervention reduced costs by 15%" (Lee, 2021).`

For each one, record:

- the claim text
- the cited source
- the type of claim

Useful claim types:

- direct quote
- numerical claim
- paraphrased finding

### Step 2 — Locate the Cited Source

Find the cited source document before checking the claim.

If the source is not available, mark the claim as unable to verify rather than guessing.

Example:

```text
Claim: the rate increased by 20%
Source: Smith (2023)
Status: source located
```

### Step 3 — Find the Relevant Source Content

Search the source for the part that should support the claim.

Examples:

- for a direct quote, look for the quoted wording
- for a number, look for the same statistic or measurement
- for a paraphrased claim, look for the section discussing that finding

The purpose of this step is to find the source passage that the citing document seems to rely on.

### Step 4 — Compare the Claim Against the Source

Once the relevant source content is found, compare it directly against the cited claim.

Check:

- does the source actually make that claim
- do direct quotes match the source wording
- do numerical claims match the source values
- does the citation preserve the source meaning rather than taking it out of context

Examples:

- source says `20%` and the claim says `20%` -> supported
- source says `15%` and the claim says `20%` -> discrepancy
- source says `may improve` and the claim says `proves` -> discrepancy

### Step 5 — Report the Result

For each cited claim, report whether it is:

- verified
- partially supported
- not supported
- contradicted
- unable to verify

For discrepancies, explain what the source actually says.

Example:

```text
Claim: "According to Smith (2023), the rate increased by 20%."
Result: Verified
Source support: The source reports a 20% increase in the results section.
```

```text
Claim: "Lee (2021) proved the intervention eliminated errors."
Result: Not supported
Source support: The source says the intervention reduced errors, not that it eliminated them.
```

## Basic Implementation Pattern

```python
def verify_citation(claim, source_excerpt):
    if exact_match(claim, source_excerpt):
        return "verified"
    if partial_match(claim, source_excerpt):
        return "partially supported"
    if contradiction(claim, source_excerpt):
        return "contradicted"
    return "not supported"
```

## Practical Rules

### Verify the Source Directly

Do not rely on summaries of the source if the original source text is available.

### Check Quotes Word for Word

Direct quotations should match the source wording closely.

### Check Numbers Carefully

Statistics, percentages, and dates should match the cited source.

### Preserve Meaning, Not Just Keywords

A citation can reuse some source words and still misrepresent the source's actual conclusion.

### Mark Missing Sources Explicitly

If the source cannot be found, report that the claim could not be verified.

## Common Pitfalls

- checking only whether the topic appears in the source instead of whether the claim is truly supported
- verifying paraphrases too loosely
- overlooking small numerical mismatches
- accepting quoted text without comparing it to the source wording
- treating unavailable sources as if they were verified

## When NOT to Use

- the task is to summarize the sources rather than verify citations
- the document does not make source-attributed claims
- the user wants a bibliography check instead of source-support verification

## Quick Summary

```text
1. Identify each claim that cites a source
2. Locate the cited source document
3. Find the relevant source content
4. Compare the claim against what the source actually says
5. Report verified claims and discrepancies clearly
```
