# Task: User export during field migration

The task files are in `/root/task`.

This client exports user records from an API that currently serves both deprecated and current field names.

Start here:
- `/root/task/fetch_users.py`
- `/root/task/field_aliases.py`
- `/root/task/compat_projection.py`
- `/root/task/api_docs.md`

What to do:
1. Keep the existing export workflow.
2. Use the current response contract from `/root/task/api_docs.md`.
3. Do not blindly trust deprecated compatibility fields when current fields are also present.
4. Save all edits under `/root/task`.

Output contract:
- Write `/root/task/output.json` as an array of 10 user objects using the current response contract from `/root/task/api_docs.md`.
- Prefer current fields over deprecated compatibility aliases when both are present, including current `username`, `phone`, and `email`.
