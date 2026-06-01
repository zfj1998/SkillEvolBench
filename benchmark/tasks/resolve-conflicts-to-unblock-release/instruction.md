# Task: Unblock the v2.1 Release Merge

Please finish the release prep in `/root/task`.

The job was supposed to be straightforward: merge `develop` into the release branch, make sure tests still pass, and set the release version to `2.1.0`. The merge stopped with conflicts in a few release-critical files, so I need you to resolve those and leave the tree in a releasable state.

Start here:
- `/root/task/package.json`
- `/root/task/src/auth.py`
- `/root/task/CHANGELOG.md`
- `/root/task/release_checklist.md`

What I need:
1. Resolve the merge conflicts under `/root/task`.
2. Keep both the release hotfix behavior and the newer develop-branch behavior where they should coexist.
3. Update the release version to `2.1.0`.
4. Save the final files under `/root/task`.

Keep the release authentication regression tests available under `/root/task/public_tests/test_auth.py`; they should cover both the preserved rate-limiting hotfix and the `remember_me` behavior from develop.

Do not move the project outside `/root/task`, and do not replace it with a stub.
