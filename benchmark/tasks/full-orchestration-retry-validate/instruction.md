# Task: Run the Full User Workflow End-to-End

The worker in `/root/task` is supposed to run the full workflow for the request in `request.json`:
1. authenticate,
2. load the user profile,
3. choose the correct spec endpoint for that user,
4. submit the async job,
5. poll status until completion while tolerating transient 503s,
6. fetch, validate, and save the final result to `/root/task/validated_result.json`.

The starter now has separate routing, polling, and validation helpers, but the branch-selection layer still trusts a stale routing hint instead of the current user tier.

Start here:
- `/root/task/README.md`
- `/root/task/full_workflow.py`
- `/root/task/auth_session.py`
- `/root/task/spec_router.py`
- `/root/task/job_poller.py`
- `/root/task/result_validator.py`
- `/root/task/mock_api.py`
- `/root/task/request.json`

What I need:
1. Keep the full end-to-end sequence intact.
2. Route premium users to the premium spec path.
3. Retry the transient 503 during polling and keep waiting until the job is completed.
4. Validate the final result against the selected spec and save it.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Read `request.json` and write `/root/task/validated_result.json`.
- The saved object must be a validated premium result with `approved`, `checksum`, and `tier` fields.
- The workflow must authenticate, fetch the user, choose the correct branch, submit the async job, retry transient status 503s, poll until completion, validate the result, and then save it.
