# Task: Process Each User's Offers Through the Correct Branch

The worker in `/root/task` needs to process a small batch of users end-to-end:
1. load the target user ids,
2. fetch each user profile,
3. choose the correct offers API based on that user's status,
4. transform the offers payload,
5. save the final rows to `/root/task/offers_output.json`.

The starter has already been split into helper modules, but the branch selection still leans on an older account-field convention, so not every user goes through the right path.

Start here:
- `/root/task/README.md`
- `/root/task/offers_pipeline.py`
- `/root/task/offer_router.py`
- `/root/task/offer_formatter.py`
- `/root/task/mock_api.py`
- `/root/task/users.json`

What I need:
1. Process all three users.
2. Send premium users to the premium offers endpoint and standard users to the standard endpoint.
3. Preserve the per-user branch-specific output.
4. Save the final rows to `/root/task/offers_output.json`.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.
