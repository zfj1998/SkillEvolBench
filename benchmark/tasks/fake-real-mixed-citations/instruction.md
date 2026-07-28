# Task: E5-LS3-T5-fake-real-mixed-citations

The task files are in `/root/task`.

Verify all bibliography entries and identify any fabricated citations.

The starter audit is intentionally shallow; improve the pipeline and policy files rather than writing a static report.
Output contract: write `/root/task/output/citation_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Audit all bibliography entries and use this label taxonomy:

- `valid`: the source exists, is authentic, and supports the claim as written.
- `misrepresented`: the source exists, but the claim distorts its attribution,
  result, or scope.
- `selective`: the source partly supports the claim, but a material caveat or
  limitation was omitted.
- `fake`: the citation is fabricated, explicitly marked inauthentic, or its
  source identifier does not resolve in the verified registry.

Every entry must receive one of these four labels. Put finer distinctions such
as a missing registry record or malformed DOI in `reason` or an optional
`problem_type` field rather than inventing an additional top-level label.
