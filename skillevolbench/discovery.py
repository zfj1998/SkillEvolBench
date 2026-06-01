"""Asset discovery: scan ``benchmark/skills/`` and ``benchmark/tasks/``.

The on-disk layout is intentionally a *thin overlay* on top of the existing
Harbor/Anthropic Skill format:

* skills:  ``benchmark/skills/<slug>/SKILL.md`` (Anthropic) +
           ``benchmark/skills/<slug>/meta.yaml`` (SkillEvolBench overlay)
* tasks:   ``benchmark/tasks/<slug>/task.toml`` (Harbor) +
           ``benchmark/tasks/<slug>/instruction.md`` +
           ``benchmark/tasks/<slug>/environment/Dockerfile`` +
           ``benchmark/tasks/<slug>/tests/test.sh`` +
           ``benchmark/tasks/<slug>/task-spec.yaml`` (SkillEvolBench overlay)

This module is read-only — it never mutates the benchmark directory.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from skillevolbench.schemas.task import (
    SkillFamilyMeta,
    TaskSpec,
)


# ---------------------------------------------------------------------------
# In-memory registries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskTomlMetadata:
    """The relevant subset of fields parsed from ``task.toml [metadata]``."""

    task_id: str
    environment: str   # e.g. "code-debugging-modification"
    skill_id: str      # e.g. "E1-LS1"
    skill: str         # e.g. "systematic-error-diagnosis"
    split: str         # "learning" | "evaluation"
    role: str          # "canonical" | "enriched" | ...
    difficulty: str | None
    gap_exposure: str | None


def parse_task_toml_metadata(task_toml_path: Path) -> TaskTomlMetadata:
    data = tomllib.loads(task_toml_path.read_text())
    md = data.get("metadata", {})
    required = ["task_id", "environment", "skill_id", "skill", "split", "role"]
    missing = [k for k in required if k not in md]
    if missing:
        raise ValueError(
            f"{task_toml_path}: missing required [metadata] keys: {missing}"
        )
    return TaskTomlMetadata(
        task_id=md["task_id"],
        environment=md["environment"],
        skill_id=md["skill_id"],
        skill=md["skill"],
        split=md["split"],
        role=md["role"],
        difficulty=md.get("difficulty"),
        gap_exposure=md.get("gap_exposure"),
    )


def parse_skill_md_frontmatter_text(text: str, *, source: str = "<text>") -> dict:
    """Parse YAML frontmatter from a SKILL.md string.

    Used when the markdown content is already in memory (e.g. inside an
    in-flight ``SkillPatch.upsert_files``) and we don't want a disk
    round-trip. Falls back to permissive line-by-line key:value extraction
    when the frontmatter is technically invalid YAML.
    """
    if not text.startswith("---\n"):
        raise ValueError(f"{source}: missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"{source}: unterminated YAML frontmatter")
    frontmatter = text[4:end]
    try:
        parsed = yaml.safe_load(frontmatter) or {}
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        pass
    # Permissive fallback: top-level "key: value" lines plus a single
    # "metadata:" block whose entries are 2-space indented.
    out: dict[str, object] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    for raw in frontmatter.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("metadata:"):
            in_metadata = True
            continue
        if in_metadata and raw.startswith("  "):
            stripped = raw.strip()
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                metadata[k.strip()] = v.strip().strip('"').strip("'")
            continue
        in_metadata = False
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    if metadata:
        out["metadata"] = metadata
    return out


def parse_skill_md_frontmatter(skill_md_path: Path) -> dict:
    """Parse YAML frontmatter from an Anthropic-style SKILL.md on disk."""
    return parse_skill_md_frontmatter_text(
        skill_md_path.read_text(), source=str(skill_md_path)
    )


# ---------------------------------------------------------------------------
# Top-level registry
# ---------------------------------------------------------------------------


@dataclass
class SkillFamilyRecord:
    slug: str
    folder: Path
    meta: SkillFamilyMeta
    skill_md_frontmatter: dict


@dataclass
class TaskRecord:
    slug: str
    folder: Path
    spec: TaskSpec
    toml_metadata: TaskTomlMetadata
    # When True, this is a within-env replay of an already-executed task.
    # Scheduler emits these after each env's 30 originals (when
    # ``baseline.within_env_replay``); job_builder suffixes the runtime
    # dir + task_id with ``__replay``; hooks branch to skip
    # inject_curated / induce_skill / strategy.decide and treat the
    # library as frozen for the replay's duration.
    is_replay: bool = False


class TaskRegistry:
    """In-memory registry of all 30 skill families and 180 tasks."""

    def __init__(
        self,
        families: dict[str, SkillFamilyRecord],
        tasks_by_id: dict[str, TaskRecord],
        tasks_by_slug: dict[str, TaskRecord],
    ):
        self._families = families              # family_id -> record
        self._tasks_by_id = tasks_by_id        # task_id   -> record
        self._tasks_by_slug = tasks_by_slug    # task_slug -> record

    # ----- Constructors -----

    @classmethod
    def from_disk(
        cls,
        skills_root: Path,
        tasks_root: Path,
    ) -> "TaskRegistry":
        families = _load_families(skills_root)
        tasks = _load_tasks(tasks_root, families)

        tasks_by_id = {t.spec.task_id: t for t in tasks}
        tasks_by_slug = {t.slug: t for t in tasks}
        if len(tasks_by_id) != len(tasks):
            raise ValueError("Duplicate task_id detected in benchmark/tasks")
        if len(tasks_by_slug) != len(tasks):
            raise ValueError("Duplicate task_slug detected in benchmark/tasks")
        return cls(families, tasks_by_id, tasks_by_slug)

    # ----- Read API -----

    @property
    def families(self) -> list[SkillFamilyRecord]:
        return list(self._families.values())

    @property
    def tasks(self) -> list[TaskRecord]:
        return list(self._tasks_by_id.values())

    def family(self, family_id: str) -> SkillFamilyRecord:
        return self._families[family_id]

    def task(self, task_id: str) -> TaskRecord:
        return self._tasks_by_id[task_id]

    def task_by_slug(self, slug: str) -> TaskRecord:
        return self._tasks_by_slug[slug]

    def families_in_env(self, env_id: str) -> list[SkillFamilyRecord]:
        return sorted(
            (f for f in self._families.values() if f.meta.environment_id == env_id),
            key=lambda f: f.meta.family_id,
        )

    def tasks_in_family(self, family_id: str) -> list[TaskRecord]:
        return sorted(
            (t for t in self._tasks_by_id.values() if t.spec.family_id == family_id),
            key=lambda t: t.spec.task_index,
        )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_families(skills_root: Path) -> dict[str, SkillFamilyRecord]:
    if not skills_root.exists():
        raise FileNotFoundError(skills_root)
    out: dict[str, SkillFamilyRecord] = {}
    for folder in sorted(skills_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        meta_path = folder / "meta.yaml"
        skill_md_path = folder / "SKILL.md"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing meta.yaml in {folder}")
        if not skill_md_path.exists():
            raise FileNotFoundError(f"Missing SKILL.md in {folder}")
        meta_dict = yaml.safe_load(meta_path.read_text()) or {}
        meta = SkillFamilyMeta.model_validate(meta_dict)
        if meta.slug != folder.name:
            raise ValueError(
                f"meta.yaml slug={meta.slug!r} does not match folder name {folder.name!r}"
            )
        frontmatter = parse_skill_md_frontmatter(skill_md_path)
        out[meta.family_id] = SkillFamilyRecord(
            slug=folder.name,
            folder=folder,
            meta=meta,
            skill_md_frontmatter=frontmatter,
        )
    return out


def _load_tasks(
    tasks_root: Path,
    families: dict[str, SkillFamilyRecord],
) -> list[TaskRecord]:
    if not tasks_root.exists():
        raise FileNotFoundError(tasks_root)

    family_by_skill_slug = {f.slug: f for f in families.values()}

    out: list[TaskRecord] = []
    for folder in sorted(tasks_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        toml_path = folder / "task.toml"
        spec_path = folder / "task-spec.yaml"
        if not toml_path.exists():
            raise FileNotFoundError(f"Missing task.toml in {folder}")
        if not spec_path.exists():
            raise FileNotFoundError(f"Missing task-spec.yaml in {folder}")
        md = parse_task_toml_metadata(toml_path)
        spec_dict = yaml.safe_load(spec_path.read_text()) or {}
        spec = TaskSpec.model_validate(spec_dict)

        # Cross-check task.toml metadata vs task-spec.yaml
        if spec.task_id != md.task_id:
            raise ValueError(
                f"{folder}: task-spec.task_id={spec.task_id} != task.toml task_id={md.task_id}"
            )
        if spec.role.value != md.role:
            raise ValueError(
                f"{folder}: task-spec.role={spec.role.value} != task.toml role={md.role}"
            )
        if spec.task_slug != folder.name:
            raise ValueError(
                f"{folder}: task-spec.task_slug={spec.task_slug} != folder {folder.name}"
            )
        if md.skill not in family_by_skill_slug:
            raise ValueError(
                f"{folder}: task.toml skill={md.skill!r} has no matching skill family"
            )
        family = family_by_skill_slug[md.skill]
        if spec.family_id != family.meta.family_id:
            raise ValueError(
                f"{folder}: task-spec.family_id={spec.family_id} != "
                f"family for skill={md.skill!r} ({family.meta.family_id})"
            )
        if spec.latent_skill_id != family.meta.latent_skill_id:
            raise ValueError(
                f"{folder}: task-spec.latent_skill_id != family.latent_skill_id"
            )
        out.append(TaskRecord(slug=folder.name, folder=folder, spec=spec, toml_metadata=md))
    return out


# ---------------------------------------------------------------------------
# Asset path conventions
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Default repo root (the directory containing ``benchmark/``)."""
    here = Path(__file__).resolve().parent
    return here.parent


def default_skills_root() -> Path:
    return repo_root() / "benchmark" / "skills"


def default_tasks_root() -> Path:
    return repo_root() / "benchmark" / "tasks"
