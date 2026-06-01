The sync pipeline is staged:

1. authenticate
2. list record ids
3. fetch details
4. enrich
5. save

The detail fetch can fail transiently. Upstream results remain valid for the current sync attempt, so rerunning the full pre-detail stage is unnecessary.
