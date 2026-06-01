"""Replay store: per-task json + sqlite index.

Layout::

    stores/replay/
        replay.db                    # sqlite index (fast queries)
        records/<task_id>.json       # full ReplayRecord (deep content)

Persists one row per trial. Sqlite indexes ``family_id`` / ``env_id`` /
``task_role`` for fast filtering. The full ``ReplayRecord`` (including the
compacted trajectory dict) lives in the per-task json file pointed to by
``replay.db.replay_records.json_path``.

Read API patterns:

* ``get(task_id)``                  -> single ReplayRecord
* ``tasks_by_family(family_id)``    -> ordered by timestamp
* ``all_records()``                  -> full dump for ReportGenerator
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from skillevolbench.schemas import ReplayRecord


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS replay_records (
    task_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    task_role TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    library_hash_pre TEXT,
    library_hash_post TEXT,
    verifier_passed INTEGER NOT NULL,
    reward REAL NOT NULL,
    json_path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_replay_family    ON replay_records(family_id);
CREATE INDEX IF NOT EXISTS idx_replay_env       ON replay_records(env_id);
CREATE INDEX IF NOT EXISTS idx_replay_role      ON replay_records(task_role);
CREATE INDEX IF NOT EXISTS idx_replay_timestamp ON replay_records(timestamp);

CREATE TABLE IF NOT EXISTS skills_used (
    task_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    PRIMARY KEY (task_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skills_used_skill ON skills_used(skill_id);
"""


class ReplayStore:
    """Sqlite + per-task json persistence."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.records_dir = self.root / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "replay.db"
        # check_same_thread=False is safe here because the lifelong protocol
        # enforces n_concurrent_trials=1 (one writer at a time). Harbor's
        # hook dispatch uses ``asyncio.to_thread`` which would otherwise
        # trip sqlite3's default same-thread guard.
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA_SQL)
        self._db.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def persist(self, record: ReplayRecord) -> None:
        """Atomically write json + index row. Replaces any prior row for the
        same ``task_id`` (a re-run overrides the previous record)."""
        json_path = self.records_dir / f"{record.task_id}.json"
        json_path.write_text(record.model_dump_json(indent=2))

        self._db.execute(
            "INSERT OR REPLACE INTO replay_records "
            "(task_id, family_id, env_id, task_role, timestamp, "
            " library_hash_pre, library_hash_post, verifier_passed, reward, json_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.task_id,
                record.family_id,
                record.env_id,
                record.task_role,
                record.timestamp.isoformat(),
                record.library_hash_pre,
                record.library_hash_post,
                int(record.outcome.verifier_passed),
                record.outcome.reward,
                str(json_path),
            ),
        )
        # Refresh skills_used: drop existing rows for the task, then re-insert.
        self._db.execute("DELETE FROM skills_used WHERE task_id = ?", (record.task_id,))
        for skill_id in record.skills_actually_used:
            self._db.execute(
                "INSERT OR IGNORE INTO skills_used (task_id, skill_id) VALUES (?, ?)",
                (record.task_id, skill_id),
            )
        self._db.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def has(self, task_id: str) -> bool:
        cur = self._db.execute(
            "SELECT 1 FROM replay_records WHERE task_id = ?", (task_id,)
        )
        return cur.fetchone() is not None

    def get(self, task_id: str) -> ReplayRecord:
        row = self._db.execute(
            "SELECT json_path FROM replay_records WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._load_record(Path(row["json_path"]))

    def tasks_by_family(self, family_id: str) -> list[ReplayRecord]:
        rows = self._db.execute(
            "SELECT json_path FROM replay_records WHERE family_id = ? "
            "ORDER BY timestamp",
            (family_id,),
        ).fetchall()
        return [self._load_record(Path(r["json_path"])) for r in rows]

    def tasks_by_env(self, env_id: str) -> list[ReplayRecord]:
        rows = self._db.execute(
            "SELECT json_path FROM replay_records WHERE env_id = ? "
            "ORDER BY timestamp",
            (env_id,),
        ).fetchall()
        return [self._load_record(Path(r["json_path"])) for r in rows]

    def tasks_by_role(self, role: str) -> list[ReplayRecord]:
        rows = self._db.execute(
            "SELECT json_path FROM replay_records WHERE task_role = ? "
            "ORDER BY timestamp",
            (role,),
        ).fetchall()
        return [self._load_record(Path(r["json_path"])) for r in rows]

    def all_records(self) -> list[ReplayRecord]:
        rows = self._db.execute(
            "SELECT json_path FROM replay_records ORDER BY timestamp"
        ).fetchall()
        return [self._load_record(Path(r["json_path"])) for r in rows]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ReplayStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_record(path: Path) -> ReplayRecord:
        return ReplayRecord.model_validate(json.loads(path.read_text()))


__all__ = ["ReplayStore"]
