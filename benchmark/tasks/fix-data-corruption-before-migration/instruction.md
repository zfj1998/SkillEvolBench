# Run the migration and make sure the timeline stays correct

The migration project is in `/root/task`. The request sounds simple: run the `updated_at` backfill and verify the report timeline still lines up with the known event history. Right now the migration completes, but the reported timestamps are off.

Please update the existing code in place:
- the migration should still complete successfully
- the report timeline must match the known event hours
- do not ignore the verification step

Start here:
- `/root/task/config.py`
- `/root/task/models.py`
- `/root/task/migrate.py`
- `/root/task/report.py`
- `/root/task/verify_times.py`

Keep everything under `/root/task`. Do not replace the migration with a fake result.

Deliverable note: no standalone output file is required. The required artifacts are the edited migration/reporting source files under `/root/task`. The verifier checks the runtime report timeline object produced by the existing code; preserve its event-hour fields and chronology.
