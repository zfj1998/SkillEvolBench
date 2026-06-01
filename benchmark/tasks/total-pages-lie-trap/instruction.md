# Task: Retrieve the Full Set of Monthly Reports

The reporting client in `/root/task` pulls report pages from an API that can grow while pagination is already in progress.

The current implementation precomputes a page plan from the first response and never revisits that metadata, which is exactly the behavior that causes missing pages in production.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/page_plan.py`
- `/root/task/report_cache.py`
- `/root/task/mock_api.py`
- `/root/task/docs/reporting-api-notes.md`

What I need:
1. Retrieve all pages, even if the API metadata changes mid-run.
2. Avoid hardcoding the initial `total_pages` value as the final truth.
3. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of report objects. The provided API eventually exposes 8 pages and 80 total report rows.
- Write `trace.json` as an object with a `trace` array recording page requests and page metadata. The run should continue through page 8 if later metadata extends the total page count.
