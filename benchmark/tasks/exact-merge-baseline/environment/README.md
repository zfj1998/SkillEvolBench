# T2 Starter Notes

This baseline task uses a strict exact merge on `employee_id`.

What still makes it realistic:

- the two systems disagree on `dept` for 20 employees
- the merged master must keep fields from both sources
- the conflict log needs enough detail for an auditor to understand what happened

The starter already joins on the right key, but its conflict logging is incomplete and
under-reports known disagreements.
