# Task: Extract structured fields from five differently formatted resumes

The task files are in `/root/task`.

HR wants one unified JSON export for five resumes that arrive in different layouts:
- a table-like markdown resume
- a key-value bullet resume
- a paragraph-style narrative resume
- a mixed-format resume
- a numbered outline resume

The current extractor handles the explicit label-heavy formats, but it falls down on narrative and mixed layouts.

Start by reading:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/resume_loader.py`
- `/root/task/section_router.py`

What to deliver:
1. Extract `name`, `email`, `phone`, `education[]`, `work_experience[]`, and `skills[]` for all five resumes.
2. Keep the output schema unified across all source layouts.
3. Correctly parse multi-entry education/work history from paragraph and mixed resumes.

Save all edits under `/root/task`. Do not replace the task with hardcoded answers.

## Required Outputs and Schema
Write `/root/task/output.json`. The top-level JSON object must contain `resumes`, an array of exactly 5 resume objects.
Each resume object must include `source`, `name`, `email`, `phone`, `education`, `work_experience`, and `skills`. `education` entries use `school`, `degree`, and date/year fields when present. `work_experience` entries use `company`, `title` or `role`, and date/duration fields when present. Paragraph-style resumes must extract multiple education and work-experience entries rather than treating the whole paragraph as one field.
