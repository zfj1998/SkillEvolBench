# T4 Starter Notes

The user only asked to "clean up the customer list", but the folder contains three exports:

- `crm_export.csv`
- `newsletter_list.csv`
- `event_attendees.csv`

This is a discovery task as much as a merge task. The pipeline should:

1. discover the source files
2. normalize them into one schema
3. deduplicate by email
4. retain the most complete fields
5. write a compact audit

The starter discovery layer still behaves like an old allowlist and misses one of the
source files.
