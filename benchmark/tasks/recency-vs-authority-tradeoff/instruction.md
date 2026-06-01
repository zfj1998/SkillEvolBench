# Task: Estimate the current AI chip market size

The task files are in `/root/task`.

Use the available sources to estimate the **current** AI chip market size.
The starter policy overweights authority and underweights recency.

Save the result to `/root/task/output/market_estimate.json`.
Output contract: write `/root/task/output/market_estimate.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Because the estimate must be current, the reasoning should explain when older high-citation sources are deprioritized in favor of newer market evidence.

Use source metadata when filtering candidates. The relevant market source domain for this task is `ai_chip_market`; do not let older general semiconductor or authority-only sources dominate when newer AI-chip-market evidence is available.
