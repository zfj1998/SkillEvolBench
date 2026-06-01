# Fix the Poetry dependency conflict in this monorepo

The monorepo is in `/root/task/monorepo`. `poetry install` fails when we try to set up the worker package because the workspace packages no longer agree on a shared dependency stack.

Please fix the dependency conflict in place without breaking the existing packages. Save your edits under `/root/task/monorepo`.

The final workspace should install with one compatible Pydantic major version across `core`, `api`, and `worker`. If the API package's web framework is the source of the transitive conflict, upgrade it to a Pydantic-v2-compatible release and migrate any affected validator/configuration syntax instead of pinning different Pydantic versions in different packages or bypassing dependency resolution.

Useful paths:
- `/root/task/monorepo/poetry_error.txt`
- `/root/task/monorepo/pyproject.toml`
- `/root/task/monorepo/packages/core/pyproject.toml`
- `/root/task/monorepo/packages/api/pyproject.toml`
- `/root/task/monorepo/packages/worker/pyproject.toml`

Deliverable note: this is a dependency-resolution task, not a custom structured-output task. The required artifacts are the edited monorepo files under `/root/task/monorepo`, including a regenerated `poetry.lock` that reflects one compatible dependency stack across packages.
