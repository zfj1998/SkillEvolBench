This fixture simulates a lightweight employee profile consolidation job.

- `hr_system.json` acts as the system of record.
- `slack_profile.json` reflects user-maintained profile data.
- `company_directory.json` mirrors downstream directory sync output.

The starter intentionally suppresses one linked conflict class to mimic an overly
aggressive "reduce noisy alerts" policy. That policy is now routed through a linked
metadata map, so one bad suppression setting can hide more than one real conflict.
