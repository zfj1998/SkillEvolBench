# E4-LS4-T3 — Distinguish Structural Reordering from True Content Changes

The task files are in `/root/task`.

You are maintaining a specification review helper that compares `spec_v1.md` and
`spec_v2.md`. In this scenario the document was reorganized, not rewritten, so the
tool must recognize moved sections without falsely reporting deletions or additions.

The current starter still compares by position only. Fix it in place so the report
explains the reordering and confirms that the content itself did not change.

Relevant files:
- `/root/task/analyze_spec_reorg.py`
- `/root/task/section_index.py`
- `/root/task/reorder_detector.py`
- `/root/task/spec_v1.md`
- `/root/task/spec_v2.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/spec_reorg_report.md` (`/root/output/spec_reorg_report.md` in the default container layout).
The markdown must contain an analysis section that explicitly says the document was reordered/reorganized/moved and that there are no content changes. Include a section mapping from old section letters to new positions, such as `A -> 4`, and avoid describing unchanged content as deleted or removed.

