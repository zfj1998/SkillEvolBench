# Fix the React 18 dependency conflict in this frontend app

The app lives in `/root/task/frontend-app`. After upgrading to React 18, `npm install` now fails with an `ERESOLVE` peer dependency error. The exact install output is in `/root/task/eresolve_error.txt`.

Please fix the dependency issue in place so install is clean and the app still works correctly on React 18. Save your edits under `/root/task/frontend-app`.

The install should resolve peer dependencies cleanly. Do not use `npm install --force`, `--legacy-peer-deps`, or other flags that ignore peer dependency conflicts; update compatible dependency versions and application code instead.

Start with:
- `/root/task/eresolve_error.txt`
- `/root/task/frontend-app/package.json`
- `/root/task/changelogs/ui-components-changelog.md`

Deliverable note: this is a dependency/code compatibility task, not a custom structured-output task. The required artifact is the updated frontend project under `/root/task/frontend-app`, including `package.json` and any source compatibility edits needed for clean React 18 install and tests.
