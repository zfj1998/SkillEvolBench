# Task: Repair The German Contact Sort Order

The files for this task are under `/root/task`.

The DACH contact export in `/root/task/german_contacts.csv` needs to be sorted alphabetically for
German users, but the current implementation in `/root/task/process_contacts.py` is still using a
plain Unicode-oriented key.

What you should do:
1. Fix the sorting logic so the output follows German phonebook ordering.
2. Keep the full dataset and save the ordered contacts to `/root/task/output.json`.
3. Make sure the sort works for names with umlauts and `ß`, not just ASCII names.

Please update the code in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of contacts retained.
- `records` (array of objects): all contact records sorted by German collation rules, preserving the original contact fields.

Design contract: implement a reusable `german_sort_key` in `collation_policy.py`. It must normalize German characters for sorting (`ä`/`Ä` -> `ae`, `ö`/`Ö` -> `oe`, `ü`/`Ü` -> `ue`, `ß` -> `ss`) and `process_contacts.py` must sort by that key. Contacts such as `Bär`, `Köhler`, and `Müller` should appear in their German alphabetic sections, not after `Z`.

