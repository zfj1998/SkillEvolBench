# Quarterly Revenue Pipeline

The source file is a transaction export that has already passed schema checks, so this task is about result sanity rather than CSV parsing.

Important notes:
- quarterly totals should be directionally stable
- large jumps should be investigated before publishing
- duplicate imports can arrive under different batch IDs
- the corrected report should preserve unaffected quarters exactly as they were
