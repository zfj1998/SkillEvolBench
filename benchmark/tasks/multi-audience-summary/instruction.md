# Task: E5-LS4-T3-multi-audience-summary

The task files are in `/root/task`.

Write separate summaries for technical, management, and client audiences, each at or below 300 words.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Write distinct technical, management, and client summaries, each with selected_sections and word_count, focusing on the audience-specific concerns.

The selected sections should demonstrate audience-specific prioritization rather than document-order compression: technical coverage should select `technical_arch`, management coverage should select `management_roi`, and client coverage should select `client_value`. Across the summaries, preserve the core concepts `kubernetes`, `roi`, `user`, and `migration`, while omitting low-value background such as appendix tables and background history. The implementation should use `priority_policy.py`, `audience_policy.py`, and `summarizer.py` to produce structured `summary.json`; avoid fixed opening slices such as taking the first three sections.
