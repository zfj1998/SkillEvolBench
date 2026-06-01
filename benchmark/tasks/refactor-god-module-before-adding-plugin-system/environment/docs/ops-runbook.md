# Ops Runbook

Noise context:
- S3 archival pipeline emits a `shipment_id`.
- The old cron job still writes gzipped snapshots.
- A future Kafka sink may replace file output.

The task does not require S3, cron, or Kafka work.
