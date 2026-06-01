# Task: E5-LS4-T6-hierarchical-series-summarization

The task files are in `/root/task`.

Create per-article summaries, group summaries, and an overall synthesis for the five-document series.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Produce five per-article summaries, two group summaries, and one overall synthesis with selected_sections and word counts at each level. The summary must retain the required evidence terms and selected sections specified by the task data: do not omit the section identifiers that the starter policy marks as `must_select`, include the required thematic terms in the relevant article/group/overall summaries, and avoid forbidden off-topic terms called out by the policy files.
