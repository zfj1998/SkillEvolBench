# Task: Employee Statistics

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Calculate the average age, average salary, and average site temperature from `/root/task/employee_data.csv`, then save the validated summary to `/root/task/output.json`.

This HR export mixes real values with documented sentinel values. Use `/root/task/data_dictionary.md` to interpret those values correctly before computing any averages.

Review these files before you change anything:

- `/root/task/data_dictionary.md`
- `/root/task/employee_data.csv`
- `/root/task/schema_cleaner.py`
- `/root/task/sentinel_registry.py`
- `/root/task/summarize_employee_metrics.py`

The output should contain the three averages plus supporting metadata that shows how many special values were filtered for each metric.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `average_age`, `average_salary`, and `average_temperature` (numbers).
- `valid_counts` (object): includes `salary_zero_count` and may include other valid-count audit fields.
- `sentinel_counts` (object): includes `age_missing` for `age=-1` and `temperature_missing` for `temperature=-999`.

Design contract: use `data_dictionary.md`. Treat `age=-1` and `temperature=-999` as missing, but keep `salary=0` as a valid salary value; never replace every zero with null.

