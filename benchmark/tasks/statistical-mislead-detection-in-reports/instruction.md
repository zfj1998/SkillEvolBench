# E4-LS4-T2 — Audit Draft vs Published Report for Statistical Misleading

The task files are in `/root/task`.

This audit helper compares an internal quarterly-report draft against the published
version. The starter already notices wording changes, but it still treats semantic
distortions as ordinary edits instead of explaining why they are misleading.

Fix the pipeline so it produces a claim-by-claim audit with evidence from the draft and
an assessment of whether the published wording misrepresents the underlying numbers.

Relevant files:
- `/root/task/audit_report_changes.py`
- `/root/task/claim_registry.py`
- `/root/task/semantic_checks.py`
- `/root/task/report_draft.md`
- `/root/task/report_published.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/report_audit.md` (`/root/output/report_audit.md` in the default container layout).
Use one section per changed claim, with headings like `## 1. ...`. Each section must include the original/draft wording, published wording, evidence, and `Assessment: misleading` or `Assessment: accurate`. Flag at least three misleading claims and include evidence for small base effects (100 to 400), sample size (`20 customers` or `n=20`), inflation around 6%, a 7-day/30-day window issue, and selected competitors. Unchanged accurate claims, such as operating costs, must not be marked misleading.

