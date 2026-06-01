# E4-LS3-T1 — Fill an HR Form from the Export

The task files are in `/root/task`.

You have a small HR form-filling utility that reads `hr_data.md`, maps the labeled
fields into `template.json`, and writes `output/employee_form_filled.json`.

The current implementation is close, but the extraction contract is too brittle for
real export variants. Fix the starter in place so the template fill works reliably
without hardcoding employee values.

Relevant files:
- `/root/task/fill_employee_form.py`
- `/root/task/field_contract.py`
- `/root/task/hr_data.md`
- `/root/task/template.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/output/employee_form_filled.json` and `/root/output/employee_form_audit.json`.
The filled form JSON must use the exact keys from `template.json`, with no extra or missing keys: `name`, `id`, `department`, `start_date`, `salary`, `manager`, and `office`. All values are strings; `start_date` must be normalized to `YYYY-MM-DD`. `employee_form_audit.json` must be an object with a `resolved_labels` object whose keys are the same template fields and whose values are the source labels used to fill each field, including aliases such as `Start_Date` for `start_date`.
