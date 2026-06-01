# Planned upgrade

The team needs **alembic 1.12+** for newer migration features. That change also forces an upgrade to **SQLAlchemy 2.0**.

Known migration notes:
- `postgres://` URLs should be replaced with `postgresql://`
- `engine.execute(...)` is removed in SQLAlchemy 2.0
- bare SQL strings should be wrapped in `text(...)`
- writes should use an explicit session and `commit()`
