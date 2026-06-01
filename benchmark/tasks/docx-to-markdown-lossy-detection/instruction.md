# Task: Convert DOCX to Markdown and report information that cannot be represented cleanly

The task files are in `/root/task`.

The migration target is Git-friendly Markdown, but the source document includes elements that may be lossy in Markdown. You need two outputs:
- `document.md`
- `loss_report.json`

Start by reading:
- `/root/task/source.docx`
- `/root/task/source_features.json`
- `/root/task/convert_docx.py`
- `/root/task/loss_registry.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/document.md` and `/root/task/loss_report.json`.
`document.md` must preserve the readable document text, including the visible headings and key phrases from the source such as `Migration Design Notes`, `legacy`, and `critical risks`. `loss_report.json` must be a JSON array; each item must include `element_type` and `description` for content that cannot be represented faithfully in Markdown. Report all lossy entries from `source_features.json` whose type is registered as lossy, including at least `merged_table_cell`, `footnote`, `textbox`, and `highlight`. Do not mark ordinary bold text as lost. The converter must not slice the lossy feature list down to only the first item.
