# Task: Repair The Employee Ranking Sort

The files for this task are under `/root/task`.

HR needs `/root/task/employees.csv` sorted by department ascending and salary descending, and for
employees with the same department and salary, the original feed order must be preserved.

What you should do:
1. Fix the existing sort pipeline in `/root/task/process_employees.py`.
2. Preserve the intended sort contract exactly, including stable ordering for ties.
3. Save the final ordered records to `/root/task/output.json`.

Please update the code in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of employees retained.
- `records` (array of objects): all employee records sorted by `department` ascending and `salary` descending.

Design contract: for rows with the same `department` and `salary`, preserve the original input order. Use a stable sort or an explicit original-position tie breaker; do not rely on an unstable SQL ordering.

