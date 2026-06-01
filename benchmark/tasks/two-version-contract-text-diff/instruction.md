# E4-LS4-T1 — Compare Two Contract Versions and Classify Every Change

The task files are in `/root/task`.

You are maintaining a contract review helper that compares `contract_v1.md` and
`contract_v2.md`, then writes a structured markdown diff report to
`output/contract_diff_report.md`.

The starter has been expanded into a small clause-indexing pipeline, but it still
under-detects inline legal edits inside long sections. Fix it in place so the report
captures the full set of additions, deletions, and modifications without flagging
unchanged sections.

Relevant files:
- `/root/task/compare_contract_versions.py`
- `/root/task/clause_index.py`
- `/root/task/change_classifier.py`
- `/root/task/contract_v1.md`
- `/root/task/contract_v2.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/contract_diff_report.md` (`/root/output/contract_diff_report.md` in the default container layout).
The markdown must list exactly eight substantive changes using headings like `## Change N`. Each change should include `Type: modified|added|deleted`, the affected section/clause, and evidence from both versions. Include changes involving expense reimbursement, dispute resolution, survival/three-year language, and six-month/liability-cap language. Do not flag unchanged sections such as Services or Warranties as changes.

