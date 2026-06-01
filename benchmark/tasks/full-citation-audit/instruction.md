# Task: E5-LS3-T6-full-citation-audit

The task files are in `/root/task`.

Conduct a complete citation audit: existence, accuracy, completeness, and authenticity.

The starter audit is intentionally shallow; improve the pipeline and policy files rather than writing a static report.
Output contract: write `/root/task/output/citation_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Run a full citation audit covering existence, authenticity, content match, caveats, and claim support for every entry.

Use the audit labels consistently:
- `valid`: the cited source exists and the article claim stays within the verified source scope.
- `misrepresented`: the source exists, but the article claim distorts attribution, significance, scope, or what the source actually says.
- `selective`: the source exists and partially supports the claim, but the article omits an important caveat, limitation, scope condition, or external-validity warning.
- `fake`: the citation is fabricated or fails authenticity checks, such as a non-matching DOI, journal, author-title combination, or source registry entry.

Every citation in the packet must receive one of these labels, a reason grounded in the source metadata or evidence files, and checks showing that existence, content match, caveats, and authenticity were considered.
