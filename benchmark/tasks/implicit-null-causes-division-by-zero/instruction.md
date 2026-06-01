# Task: Channel Conversion Rates

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Build a per-channel conversion report from the three marketing extracts in `/root/task` and save the final report to `/root/task/output.json`.

The growth team uses this report to compare conversion efficiency across channels. The raw exports are messy: some rows are duplicates from upstream retries, some channels appear under slightly different names, and some denominator fields are missing or malformed.

Review the files in `/root/task` directly. In particular:

- `/root/task/README.md`
- `/root/task/channel_metrics.csv`
- `/root/task/channel_metrics_part2.csv`
- `/root/task/channel_metrics_extra.csv`
- `/root/task/channel_schema.py`
- `/root/task/channel_dedup.py`
- `/root/task/conversion_guard.py`
- `/root/task/build_conversion_report.py`

The final JSON should include one normalized record per channel plus a small summary/audit block that makes the report trustworthy.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `channels` (array of objects): each object has `channel`, `impressions`, `clicks`, `conversions`, `conversion_rate`, `ctr`, `status`, and `audit`.
- `summary` (object): includes channel counts and counts of missing/zero denominator cases.

Design contract: handle null and zero denominators before division. Channels with missing impressions must be marked as data missing; channels with zero impressions must not produce `Infinity` or `NaN`; normal channels must keep exact conversion-rate and CTR calculations.

