# Task: Make a deeply nested minified JSON export easier to read

The task files are in `/root/task`.

The user did not ask for a specific target format, only for something substantially easier to read and understand than the one-line source file.

Start by reading:
- `/root/task/data.min.json`
- `/root/task/make_readable.py`
- `/root/task/render_plan.py`
- `/root/task/section_renderer.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/readable_output.md`.
Although the user asked only for a more readable artifact, the expected deliverable is Markdown with clear headings and table-like sections for Company, Teams, Services, Settings, and Summary. It must contain key source values such as `Northwind Analytics`, `Quarter-end snapshot`, service IDs such as `svc_17`, and flags such as `flag_159`; it should be substantially more readable than pretty-printed raw JSON.

