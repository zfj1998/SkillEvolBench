## Marketing Conversion Feed

This task reconstructs a channel-level conversion report from three raw extracts:

- `channel_metrics.csv`: the main warehouse export
- `channel_metrics_part2.csv`: incremental repair feed with header drift
- `channel_metrics_extra.csv`: small manual backfill file from the analytics team

Business expectations:

- channel names must be normalized before aggregation
- exact logical duplicate rows should be removed
- missing or malformed denominator rows must not be silently treated as zero traffic
- channels with `impressions = 0` are valid new channels, not broken rows
- the final report should stay usable even when some upstream slices are incomplete

The report should be saved to `output.json` and should contain:

- `channels`: one normalized record per channel
- `summary`: aggregate counts that explain report quality

The downstream dashboard consumes this file directly, so avoid `Infinity`, `NaN`, or crashing on channels with missing denominator data.
