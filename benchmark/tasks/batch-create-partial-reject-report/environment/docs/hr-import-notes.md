# HR Import Notes

The nightly employee import is supposed to be best-effort:
- valid rows should be created
- invalid rows should be reported with row-level detail
- later rows can fail because earlier rows already reserved a username

Operations asked for a structured summary so they can reconcile partial imports quickly.
