# Task: Review a "Successful" Merge That Still Broke Validation

The merged code in `/root/task` has no conflict markers, but the registration flow is acting wrong after the merge. Git says the merge succeeded, so this looks like a semantic conflict rather than a text conflict.

Two separate validation features landed at about the same time. Please review the merged result carefully, fix whatever broke, and keep both validation behaviors working.

Start here:
- `/root/task/app.py`
- `/root/task/validators.py`
- `/root/task/merge_review_notes.md`

What I need:
1. Check the merged code under `/root/task`.
2. Fix the semantic conflict in place.
3. Keep both email validation and phone validation available after your change. Preserve them as separately named helpers, `validate_email` and `validate_phone`, and update `app.py` so the registration flow calls the matching helper for each field.
4. Save all edits under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Deliverable note: this is a code-modification task, not a file-generation task. Do not create a separate report file; the verifier checks the edited validation code and the existing registration-flow API behavior. Preserve the existing request/response dictionary shapes while restoring both email and phone validation.
