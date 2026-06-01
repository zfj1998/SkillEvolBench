---
name: pagination-complete-retrieval
description: Retrieve the complete dataset from offset-based paginated REST APIs by fetching every page in sequence. Use this skill when an API returns results in numbered pages such as `page=1&per_page=25` and the user needs all records, not just the first page. Focus on page-number plus page-size pagination with JSON results that can be combined into one list.
metadata:
  environment: multi-step-tool-api-orchestration
  skill_id: E2-LS3
  short-description: "Retrieve the complete dataset from offset-based paginated REST APIs by fetching every page in sequence"
  version: "1.0"
---

# Pagination Complete Retrieval

Use this workflow when an API returns results in numbered pages and the goal is to fetch the full dataset rather than a single page.

Scope: offset-based pagination using page number plus page size.

## When to Use

Use this skill when:

- The API returns only part of the dataset per request
- The request supports parameters such as `page` and `per_page`
- The user asks for all records, all pages, or the complete result set
- The response can be combined page by page into one list

## Pagination Workflow

Follow these six steps in order.

### Step 1 — Make the First Request

Start with page `1` and a fixed page size.

Example:

```python
response = requests.get(
    url,
    params={"page": 1, "per_page": 25},
    timeout=30,
)
```

The first response gives you:

- the first page of results
- any pagination metadata the API exposes

### Step 2 — Check the Pagination Info

After the first response, inspect the payload for pagination details.

Common fields to look for:

- `total_pages`
- `total_count`
- `page`
- `per_page`

If the API returns only the result array and no metadata, use the number of returned items to decide when pagination is complete.

### Step 3 — Request the Next Page

If more pages remain, increment the page number and send the next request.

Example:

```python
page += 1
response = requests.get(
    url,
    params={"page": page, "per_page": per_page},
    timeout=30,
)
```

Repeat sequentially: page 1, then page 2, then page 3, and so on.

### Step 4 — Continue Until Completion

Keep fetching pages until one of these stop conditions is true:

1. the number of returned results is less than the page size
2. the current page number has reached `total_pages`

These are the expected completion signals for this pagination style.

### Step 5 — Combine All Results

Append each page's results into one master list.

Example:

```python
all_results.extend(page_results)
```

Do not return page-by-page fragments when the task requires the full dataset. The output should be one combined list.

### Step 6 — Verify Completeness

If the API provides `total_count`, verify that the merged list matches that count.

Example:

```python
if total_count is not None and len(all_results) != total_count:
    raise Exception(f"Incomplete retrieval: expected {total_count}, got {len(all_results)}")
```

If the count does match, retrieval is complete.

## Basic Implementation Pattern

A simple pattern looks like this:

```python
import requests
import time

def fetch_all_pages(url, per_page=25, delay=0.5):
    all_results = []
    page = 1
    total_pages = None
    total_count = None

    while True:
        response = requests.get(
            url,
            params={"page": page, "per_page": per_page},
            timeout=30,
        )
        data = response.json()

        if isinstance(data, list):
            page_results = data
        else:
            page_results = data.get("results", [])
            if total_pages is None:
                total_pages = data.get("total_pages")
            if total_count is None:
                total_count = data.get("total_count")

        all_results.extend(page_results)

        if len(page_results) < per_page:
            break

        if total_pages is not None and page >= total_pages:
            break

        time.sleep(delay)
        page += 1

    if total_count is not None and len(all_results) != total_count:
        raise Exception(f"Incomplete retrieval: expected {total_count}, got {len(all_results)}")

    return all_results
```

## Last-Page Handling

The final page often has fewer results than the requested page size.

Example:

- page size = `25`
- page 1 returns `25`
- page 2 returns `25`
- page 3 returns `23`

Page 3 is the last page because `23 < 25`.

If the total count is an exact multiple of the page size, the final page may still contain exactly `per_page` items. In that case, `total_pages` is the cleaner stop condition when the API provides it.

## Intermediate Progress

If the API has many pages, store progress after each successful page so a failure midway does not discard everything collected so far.

Typical progress to save:

- the merged results so far
- the next page number to request

The important point is to checkpoint after each page, not only at the very end.

## Rate-Limit Courtesy

Add a small delay between page requests to reduce the chance of hitting rate limits.

Typical fixed delays:

- `0.5` seconds
- `1.0` second

The delay belongs between successful page fetches, before the next page request.

## Common Pitfalls

- Returning only the first page when the task requires the full dataset
- Forgetting to increment the page number
- Stopping before checking whether more pages remain
- Failing to combine page results into one list
- Ignoring `total_count` when the API provides it

## When NOT to Use

- The API does not use numbered pages with a page-size parameter
- The user only wants the first page or a specific page
- The response is not meant to be aggregated into one complete list

## Quick Summary

```text
1. Request page 1
2. Read pagination info
3. Increment page number and fetch next page
4. Stop when the page is short or total_pages is reached
5. Merge all page results into one list
6. Verify len(all_results) against total_count when available
```
