# Finish the pending PR for CSV export

The code for this task is in `/root/task/project`. Please finish the pending PR described in `/root/task/project/docs/pr_description.md` and keep the existing app working.

There is also some project context in `/root/task/project/docs/context.md` and `/root/task/project/docs/ci_log.txt`. Work in place under `/root/task/project` and save your edits there.

Treat the CI/install failure described in the project context as part of the task: resolve the dependency conflict first so the project can install cleanly from the offline wheels, then implement the CSV export behavior from the PR description. The CSV endpoint and helper should handle all documented date-filter edge cases, including `start_date` only, `end_date` only, no matching records, and empty record lists.

Useful paths:
- `/root/task/project/docs/pr_description.md`
- `/root/task/project/docs/context.md`
- `/root/task/project/docs/ci_log.txt`
- `/root/task/project/requirements.txt`
- `/root/task/project/src/app.py`

If you need packages, use the offline wheels in `/root/task/local_index`.

Deliverable note: no standalone output file is required. The required artifacts are the edited files under `/root/task/project`, especially dependency files and the CSV export implementation described by the PR. The verifier checks installability, endpoint behavior, and the CSV response produced by the application.
