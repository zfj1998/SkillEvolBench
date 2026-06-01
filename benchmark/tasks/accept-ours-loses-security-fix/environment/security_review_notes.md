# Security Review Notes

Scope:
- Existing read/write queries in `database.py`
- Newly added search flow

Reviewer guidance:
- Recent review flagged string-formatted SQL in user-facing paths.
- Search support is fine to keep, but new queries should follow the same parameterized-query standard as the rest of the module.
- Be careful with merge shortcuts like "accept ours" or "accept theirs" here. Either one can silently drop something important.

Known risky inputs:
- Quotes
- Semicolons
- SQL comment markers
