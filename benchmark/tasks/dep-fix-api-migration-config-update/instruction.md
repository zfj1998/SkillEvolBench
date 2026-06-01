# Upgrade Alembic and make the SQLAlchemy stack compatible

The service code is in `/root/task/project`. We need to move to Alembic 1.12+, which forces a SQLAlchemy upgrade, and the current codebase is not compatible yet.

Please update the project in place under `/root/task/project`, fix the compatibility issues, and keep the application behavior working.

Useful paths:
- `/root/task/project/docs/error_log.txt`
- `/root/task/project/docs/migration_log.txt`
- `/root/task/project/requirements.txt`
- `/root/task/project/src/config.py`
- `/root/task/project/src/database.py`
- `/root/task/project/src/services/`

If you need packages, use the offline wheels in `/root/task/local_index`.

Deliverable note: this is a code/dependency migration task, not a separate structured-output task. The required artifacts are the edited project files under `/root/task/project`, including dependency/configuration/source changes needed for the application and migration tests to pass. Preserve the existing service return shapes and database model semantics.
