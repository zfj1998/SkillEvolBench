# E4-LS5-T1 — Merge Three Address Books Into One Master Contact List

The task files are in `/root/task`.

Operations wants one reconciled contact list built from the CRM export, the HR directory,
and the email marketing contacts. The overlap is messy:
- some people appear with nicknames (`Robert` / `Bob`, `James` / `Jim`)
- some rows are missing email in one system but still have the same phone number
- two different people share the exact same display name (`John Smith`) and must **not** be merged

Update the merge pipeline so that it produces a clean master list and a short audit report.

Relevant files:
- `/root/task/build_master_contacts.py`
- `/root/task/source_registry.py`
- `/root/task/identity_matcher.py`
- `/root/task/merge_policy.py`
- `/root/task/crm.csv`
- `/root/task/hr.csv`
- `/root/task/email_contacts.csv`
- `/root/task/README.md`

Expected outputs:
- `/root/task/master_contacts.csv`
- `/root/task/merge_report.md`
- `/root/task/merge_audit.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/master_contacts.csv`, `/root/task/merge_report.md`, and `/root/task/merge_audit.json`.
`master_contacts.csv` must include one row per unique contact with headers including `name`, `email`, `phone`, and `_sources`. Merge Bob/Robert/Bobby style variants using email/phone/nickname evidence, but keep different John Smith contacts separate. `merge_audit.json` must include `master_records`, `raw_records`, `phone_assisted_merges`, and `matcher` text mentioning phone and nickname matching. The markdown report summarizes merge counts and review notes.

