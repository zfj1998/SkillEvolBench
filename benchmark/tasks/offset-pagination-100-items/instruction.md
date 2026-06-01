# Task: Retrieve the Full User Export from the Offset API

The export job under `/root/task` is supposed to pull the full user list from a paginated API and write the final result to `output.json`.

Right now the pipeline looks reasonable on a quick read, but the exported list is still wrong when the API returns a page with a duplicated boundary row.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/offset_plan.py`
- `/root/task/mock_api.py`
- `/root/task/docs/offset-retrieval-notes.md`

What I need:
1. Retrieve all users from the API, not just most of them.
2. Keep the pagination logic generic instead of hardcoding page count.
3. Preserve order and remove duplicate ids in the final export.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of user objects with at least `id` and user fields from the API. It must contain exactly 100 unique users in API order, ids 1 through 100.
- Write `trace.json` as an object with a `trace` array. Each trace entry records the request `offset`, `limit`, and returned ids.
- With the provided API, the correct generic offset plan uses offsets `0, 20, 40, 60, 80`; do not hardcode a page count in the implementation.
