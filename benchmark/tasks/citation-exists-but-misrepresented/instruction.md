# Task: E5-LS3-T2-citation-exists-but-misrepresented

The task files are in `/root/task`.

Verify whether each citation accurately represents the source, not just whether the source exists.

The starter audit is intentionally shallow; improve the pipeline and policy files rather than writing a static report.
Output contract: write `/root/task/output/citation_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Audit all citations for existence and whether the cited source actually supports the article claim; label misrepresented citations separately from valid ones.
