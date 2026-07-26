# Task: E5-LS3-T4-implicit-fact-check

The task files are in `/root/task`.

Fact-check the article before publication and produce a structured citation audit.

The starter audit is intentionally shallow; improve the pipeline and policy files rather than writing a static report.
Output contract: write `/root/task/output/citation_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Audit all citations for authenticity, source support, and implicit fact-check issues such as overbroad or unsupported claims.

Use this label taxonomy:

- `valid`: the source exists, is authentic, and supports the claim as written.
- `misrepresented`: the source is real, but the claim is unsupported by it,
  overstates it, changes its attribution, or drops scope in a way that changes
  the claim.
- `fake`: the cited source is missing or is explicitly marked inauthentic or
  fabricated.

Do not invent additional top-level labels such as `unsupported`; record the
specific mechanism in `reason` or an optional `problem_type` field while using
the taxonomy above.
