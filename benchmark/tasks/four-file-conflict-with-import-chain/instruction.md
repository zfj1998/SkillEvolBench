# Task: Resolve the Merge Before We Cut the Utility Rollout

I merged two branches into the copy under `/root/task`, and git stopped on conflicts.

One branch renamed the shared helper to make the name clearer. The other branch added a new `mode` option because some callers need stricter processing. We need both changes, not one or the other.

Please fix the conflicted files in place under `/root/task` and make sure the whole call chain is consistent after the merge.

Start here:
- `/root/task/utils.py`
- `/root/task/routes.py`
- `/root/task/services.py`
- `/root/task/public_tests/test_utils.py`
- `/root/task/merge_summary.md`

What I need:
1. Resolve the merge conflicts.
2. Keep the new function name.
3. Keep the new `mode` parameter and update every affected call site.
   In this instance, `routes.py` should read `mode` from the request data and pass it as `mode=mode`; `services.py` should preserve the strict internal call by passing `mode="strict"`.
4. Save the finished files back under `/root/task`.

Do not move the project out of `/root/task`, and do not replace it with a stub.

Deliverable note: this is a merge/code repair task, not a structured-output task. Do not create a separate report file; the verifier checks that conflict markers are removed, imports/call sites are consistent, and the existing Python functions/tests keep their expected behavior.
