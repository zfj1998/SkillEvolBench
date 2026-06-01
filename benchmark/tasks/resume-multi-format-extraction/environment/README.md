# Resume Extraction Fixture

This fixture simulates a lightweight ATS ingestion utility.

Input documents:
- `resume_table.md`
- `resume_list.txt`
- `resume_paragraph.txt`
- `resume_mixed.md`
- `resume_outline.txt`

Code structure:
- `resume_loader.py`: discovers input files and basic layout hints
- `section_router.py`: routes each resume into an extraction strategy
- `analyzer.py`: orchestrates batch extraction and shapes the final JSON payload

Expected output:
- top-level `{"resumes": [...]}`
- one normalized JSON object per resume
- fields: `source`, `name`, `email`, `phone`, `education`, `work_experience`, `skills`

Known starter gaps:
- paragraph narrative resumes only recover one education entry
- mixed-format resumes lose part of the narrative work history
- some skill extraction still includes noisy section labels
