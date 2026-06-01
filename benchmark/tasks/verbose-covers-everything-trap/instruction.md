# Task: E5-LS4-T5-verbose-covers-everything-trap

The task files are in `/root/task`.

Summarize in no more than 500 words while preserving the highest-value findings.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Do not evenly compress every paragraph. Expand the highest-value findings, compress background/appendix material, and include selected_sections plus word_count.

The highest-value findings are the quantitative renewable-energy claims and grid/finance recommendation. The summary should include the concepts `30%`, `95%`, `tripling`, `grid`, and `finance`; select `finding_30`, `finding_solar_wind`, `finding_gap`, and `recommendation_grid`; and avoid low-value phrases such as `appendix tables` and `historical electricity statistics`. The implementation should use `priority_policy.py` and `summarizer.py` to rank sections and should not pass by taking a fixed opening slice.
