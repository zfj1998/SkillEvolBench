"""Git-versioned skill library.

Layout::

    library/
        .git/
        manifest.yaml       # git-tracked index over all skills + their history
        active/             # all skill content (active + retired) lives here
            <skill_id>/
                SKILL.md
                scripts/
                references/
        .frozen             # git-ignored marker; existence flips library to readonly
        snapshots/          # git tags accessed via SnapshotStore

The store offers two write APIs:

* ``apply_patch(patch, current_task, strategy_name)`` -- atomic upserts +
  deletes + manifest update + git commit. Refuses to run when ``.frozen``
  exists.
* ``inject_curated`` / ``create_skill`` -- specialized one-skill creation
  paths used by Part 4 hooks (Path-B injection, Self-Gen-Zero-Shot).

Read APIs:

* ``compute_hash()`` -> deterministic git tree hash. Used by the freeze
  invariant assertion in hooks (§4.5.3) and by RetrievalStore (cache key).
* ``list_active() / get_skill(id) / has_curated_for / has_seed_for``
Rollback:

* ``rollback_to(commit_hash, reason)`` -- ``git reset --hard``. Used by
  ``LibraryFreezeController`` and rollback strategies.

The store is **single-writer**. Concurrency is bounded by Harbor's
``n_concurrent_trials=1`` (validated by Part 3 ``RunConfig``).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import yaml

from skillevolbench.schemas import (
    Applicability,
    ApplyResult,
    AuthorStrategy,
    LibraryManifest,
    OperationType,
    SkillEvidence,
    SkillManifestEntry,
    SkillPatch,
    SkillStatus,
    SkillVersion,
    SkillVersionRecord,
)


_LOG = logging.getLogger(__name__)
_FROZEN_MARKER = ".frozen"
_GITIGNORE_TEMPLATE = "{}\n".format(_FROZEN_MARKER)


# ---------------------------------------------------------------------------
# skill_id <-> on-disk slug mapping
#
# Per Anthropic SKILL.md spec, the SKILL.md frontmatter ``name`` must equal the
# folder name. Our skill_ids are latent_skill_ids (e.g. ``E5-LS3.foo``) but the
# folder on disk uses just the slug (``foo``) so frontmatter ``name: foo``
# stays consistent. The mapping happens at the path-construction boundary;
# manifest / patches / events still use the full skill_id.
# ---------------------------------------------------------------------------


def skill_id_to_slug(skill_id: str) -> str:
    """``E5-LS3.foo`` -> ``foo``. Returns input unchanged if no '.' is present."""
    return skill_id.split(".", 1)[1] if "." in skill_id else skill_id


def slug_to_skill_id(slug: str, manifest: "LibraryManifest") -> Optional[str]:
    """Reverse lookup via manifest. Returns None if no match."""
    for sid in manifest.skills:
        if skill_id_to_slug(sid) == slug:
            return sid
    return None


# ---------------------------------------------------------------------------
# Git wrapper (subprocess; deterministic + works without harbor SDK)
# ---------------------------------------------------------------------------


class _GitWrapper:
    """Minimal git CLI wrapper. Used by LibraryStore + SnapshotStore.

    Configures ``user.email`` / ``user.name`` after ``git init`` so commits
    don't fail on the bot's behalf. Sets ``commit.gpgsign=false`` locally so
    contributors with global signing don't break runs.
    """

    def __init__(self, root: Path):
        self.root = root

    def _run(
        self,
        *args: str,
        check: bool = True,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.root),
            check=check,
            capture_output=capture,
            text=True,
        )

    def init(self) -> None:
        self._run("init", "-q", "-b", "main")
        self._run("config", "user.email", "skillevol@bot")
        self._run("config", "user.name", "SkillEvolBot")
        self._run("config", "commit.gpgsign", "false")

    def add_all(self) -> None:
        self._run("add", "-A")

    def commit(self, message: str) -> str:
        # ``--allow-empty`` so manifest-only patches still produce a commit.
        self._run("commit", "-q", "--allow-empty", "-m", message)
        return self.head_hash()

    def head_hash(self) -> str:
        return self._run("rev-parse", "HEAD").stdout.strip()

    def current_tree_hash(self) -> str:
        return self._run("rev-parse", "HEAD^{tree}").stdout.strip()

    def reset_hard(self, commit: str) -> None:
        self._run("reset", "--hard", commit, "-q")

    def tag(self, tag_name: str, message: str = "") -> None:
        self._run("tag", "-a", tag_name, "-m", message or tag_name)

    def has_tag(self, tag_name: str) -> bool:
        result = self._run("tag", "--list", tag_name, check=False)
        return tag_name in result.stdout.split()

    def show_tree(self, ref: str = "HEAD") -> str:
        return self._run("ls-tree", "-r", "--name-only", ref).stdout

    def initial_commit_done(self) -> bool:
        result = self._run("rev-parse", "HEAD", check=False)
        return result.returncode == 0


# ---------------------------------------------------------------------------
# LibraryStore
# ---------------------------------------------------------------------------


class LibraryStore:
    """The git-versioned global skill library."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.active_dir = self.root / "active"
        self.manifest_path = self.root / "manifest.yaml"
        self._git = _GitWrapper(self.root)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, root: Path) -> "LibraryStore":
        """Initialize an empty library at ``root``. Idempotent: returns the
        existing library when ``.git`` is already there."""
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        store = cls(root)
        if (root / ".git").exists():
            return store
        (root / "active").mkdir(exist_ok=True)
        manifest = LibraryManifest()
        store._save_manifest(manifest)
        (root / ".gitignore").write_text(_GITIGNORE_TEMPLATE)
        store._git.init()
        store._git.add_all()
        store._git.commit("Initial empty library")
        return store

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def list_active(self) -> list[SkillManifestEntry]:
        manifest = self._load_manifest()
        return [
            e for e in manifest.skills.values() if e.status == SkillStatus.ACTIVE
        ]

    def list_all(self) -> list[SkillManifestEntry]:
        return list(self._load_manifest().skills.values())

    def list_skill_ids(self) -> list[str]:
        return [e.skill_id for e in self.list_active()]

    def has_skill(self, skill_id: str) -> bool:
        return skill_id in self._load_manifest().skills

    def has_seed_for(self, family_id: str) -> bool:
        """Any non-retired skill exists for this family."""
        m = self._load_manifest()
        return any(
            e.family_id == family_id and e.status != SkillStatus.RETIRED
            for e in m.skills.values()
        )

    def has_curated_for(self, family_id: str) -> bool:
        """At least one skill in this family was seeded via curated injection."""
        m = self._load_manifest()
        for entry in m.skills.values():
            if entry.family_id != family_id:
                continue
            if not entry.versions:
                continue
            v0 = entry.versions[0]
            if v0.author_strategy == AuthorStrategy.CURATED_SEED:
                return True
        return False

    def get_manifest_entry(self, skill_id: str) -> SkillManifestEntry:
        return self._load_manifest().skills[skill_id]

    def get_skill(self, skill_id: str) -> SkillVersion:
        entry = self.get_manifest_entry(skill_id)
        skill_dir = self.active_dir / skill_id_to_slug(skill_id)
        files = self._read_skill_files(skill_dir)
        return SkillVersion(
            skill_id=skill_id,
            version=entry.current_version,
            files=files,
            manifest_entry=entry,
        )

    def skills_in_family(self, family_id: str) -> list[SkillManifestEntry]:
        m = self._load_manifest()
        return [
            e for e in m.skills.values()
            if e.family_id == family_id and e.status == SkillStatus.ACTIVE
        ]

    def compute_hash(self) -> str:
        """Deterministic git tree hash. Equal across processes for the same
        on-disk content."""
        if not self._git.initial_commit_done():
            return "uninit"
        return self._git.current_tree_hash()

    # ------------------------------------------------------------------
    # Freeze
    # ------------------------------------------------------------------

    def freeze(self) -> None:
        (self.root / _FROZEN_MARKER).touch()

    def unfreeze(self) -> None:
        marker = self.root / _FROZEN_MARKER
        if marker.exists():
            marker.unlink()

    def is_frozen(self) -> bool:
        return (self.root / _FROZEN_MARKER).exists()

    # ------------------------------------------------------------------
    # Write API: apply_patch / inject_curated / create_skill
    # ------------------------------------------------------------------

    def apply_patch(
        self,
        patch: SkillPatch,
        current_task: str,
        strategy_name: str,
    ) -> ApplyResult:
        """Apply ``patch`` atomically: upserts + deletes + manifest update + git commit.

        Refuses when ``.frozen`` exists -- that's the freeze guard.
        """
        if self.is_frozen():
            raise PermissionError(
                f"LibraryStore.apply_patch called while frozen "
                f"({self.root / _FROZEN_MARKER} exists)"
            )

        manifest = self._load_manifest()
        # Physical skill folders are keyed by slug, while the manifest is
        # keyed by latent skill id. Two families claiming the same slug would
        # otherwise overwrite one directory and create contradictory history.
        existing_slug_owner = {
            skill_id_to_slug(skill_id): skill_id for skill_id in manifest.skills
        }
        for skill_id in patch.target_skill_ids:
            slug = skill_id_to_slug(skill_id)
            owner = existing_slug_owner.get(slug)
            if owner is not None and owner != skill_id:
                raise ValueError(
                    f"skill slug {slug!r} is already owned by {owner!r}; "
                    f"cannot assign it to {skill_id!r}"
                )
        applied_upserts: list[str] = []
        applied_deletes: list[str] = []
        affected_skill_ids: set[str] = set()

        # 1. upserts
        # Convention (post-folder=slug refactor): upsert_files keys are
        # ``<slug>/SKILL.md`` (or ``<slug>/scripts/...``). target_skill_ids
        # is still the formal latent_skill_id list; we translate slug ->
        # skill_id via target_skill_ids + manifest.
        slug_to_sid = {skill_id_to_slug(s): s for s in patch.target_skill_ids}
        for sid in manifest.skills:
            slug_to_sid.setdefault(skill_id_to_slug(sid), sid)
        for rel_path, content in patch.upsert_files.items():
            target = self.active_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            applied_upserts.append(rel_path)
            slug = rel_path.split("/", 1)[0]
            sid = slug_to_sid.get(slug)
            if sid is not None:
                affected_skill_ids.add(sid)

        # 2. deletes -- mark as RETIRED in manifest AND remove from working
        # tree.
        #
        # Why unlink: with native skill auto-discovery (Harbor 0.6+ env.py
        # bind-mounts ``library/active/`` into ``~/.claude/skills/`` etc.),
        # the agent CLIs scan the directory directly and would otherwise
        # surface retired skills via Tier-1 description loading. The
        # manifest's ``status: retired`` flag is invisible to native
        # discovery, so we MUST physically remove the file to enforce
        # retirement semantics on the agent side.
        #
        # Git history is preserved regardless: ``git show <commit>:<path>``
        # can recover any prior version, and ``git log -- <path>`` lists
        # the full revision chain even after the working-tree deletion is
        # committed. Audit + replay capabilities are unaffected.
        for rel_path in patch.delete_paths:
            slug = rel_path.split("/", 1)[0]
            skill_id = slug_to_sid.get(slug)
            if skill_id and skill_id in manifest.skills:
                manifest.skills[skill_id].status = SkillStatus.RETIRED
                applied_deletes.append(rel_path)
                affected_skill_ids.add(skill_id)
                # Remove the skill directory from the working tree. Files
                # remain in git history; ``git add -A`` below will record
                # the deletion as part of this commit.
                skill_dir = self.active_dir / slug
                if skill_dir.exists():
                    import shutil
                    shutil.rmtree(skill_dir)

        # 3. manifest updates
        # Tier-1 description must come from the SKILL.md frontmatter, not
        # from patch.summary (which is a git-style audit string like
        # "Inject curated v0 for E1-LS1"). Without this, the retriever
        # embeds garbage and ranks every skill near-zero against real task
        # queries; the Available Skills prompt section also shows agents
        # the audit string instead of the actual skill description.
        description_updates = self._extract_descriptions_from_patch(
            patch, slug_to_sid
        )
        author = self._coerce_author(strategy_name)
        for skill_id in patch.target_skill_ids:
            new_desc = description_updates.get(skill_id)
            if skill_id in manifest.skills:
                self._bump_existing_skill(
                    manifest.skills[skill_id],
                    patch=patch,
                    current_task=current_task,
                    author=author,
                    new_description=new_desc,
                )
            else:
                manifest.skills[skill_id] = self._new_manifest_entry(
                    skill_id=skill_id,
                    patch=patch,
                    current_task=current_task,
                    author=author,
                    description=new_desc,
                )
            affected_skill_ids.add(skill_id)

        self._save_manifest(manifest)

        # 4. Primary commit: file changes + manifest row (without git_commit yet).
        self._git.add_all()
        commit_msg = (
            f"[{strategy_name}] {patch.summary[:80]} (task={current_task})"
        )
        primary_hash = self._git.commit(commit_msg)

        # 5. Backfill commit_hash into the manifest's just-appended versions
        #    and persist via a SECOND commit (no amend). The amend approach
        #    used to mutate the commit hash *after* the manifest had recorded
        #    it, so the recorded hash referenced an orphaned commit. Splitting
        #    into two commits keeps every recorded hash reachable: the
        #    manifest row for version N still points to the primary commit
        #    that introduced the file change, while ``ApplyResult.commit_hash``
        #    returns HEAD post-backfill so callers (rollback / event log) can
        #    refer to a single canonical state.
        backfilled = False
        for skill_id in affected_skill_ids:
            if skill_id in manifest.skills and manifest.skills[skill_id].versions:
                manifest.skills[skill_id].versions[-1].git_commit = primary_hash
                backfilled = True
        head_hash = primary_hash
        if backfilled:
            self._save_manifest(manifest)
            self._git.add_all()
            head_hash = self._git.commit(
                f"manifest: backfill commit hash for {patch.patch_id}"
            )

        return ApplyResult(
            commit_hash=head_hash,
            upserted=applied_upserts,
            deleted=applied_deletes,
            affected_skill_ids=sorted(affected_skill_ids),
        )

    def inject_curated(
        self,
        skill_md_path: Path,
        family_id: str,
        latent_skill_id: str,
        created_from_task: str,
    ) -> ApplyResult:
        """Path-B: copy a curated SKILL.md as version 1 of ``latent_skill_id``."""
        if self.is_frozen():
            raise PermissionError("inject_curated called while frozen")
        skill_md_path = Path(skill_md_path)
        content = skill_md_path.read_text()
        slug = skill_id_to_slug(latent_skill_id)
        patch = SkillPatch(
            patch_id=self._uuid(),
            summary=f"Inject curated v0 for {family_id}",
            upsert_files={f"{slug}/SKILL.md": content},
            target_skill_ids=[latent_skill_id],
            operation_type=OperationType.CREATE,
            triggered_by_task=created_from_task,
        )
        return self.apply_patch(
            patch,
            current_task=created_from_task,
            strategy_name=AuthorStrategy.CURATED_SEED.value,
        )

    def create_skill(
        self,
        skill_id: str,
        content: str,
        source: str,
        family_id: str,
        created_from_task: str,
    ) -> ApplyResult:
        """Self-Gen-Zero-Shot or induction: create a new skill from given content."""
        if self.is_frozen():
            raise PermissionError("create_skill called while frozen")
        try:
            author = AuthorStrategy(source)
        except ValueError:
            author = AuthorStrategy.INDUCTION
        slug = skill_id_to_slug(skill_id)
        patch = SkillPatch(
            patch_id=self._uuid(),
            summary=f"Create {skill_id} ({source})",
            upsert_files={f"{slug}/SKILL.md": content},
            target_skill_ids=[skill_id],
            operation_type=OperationType.CREATE,
            triggered_by_task=created_from_task,
        )
        return self.apply_patch(
            patch,
            current_task=created_from_task,
            strategy_name=author.value,
        )

    def rollback_to(self, commit_hash: str, reason: str = "") -> None:
        """git reset --hard. The manifest.yaml in working tree is restored."""
        if self.is_frozen():
            raise PermissionError("rollback_to called while frozen")
        self._git.reset_hard(commit_hash)
        _LOG.info(
            "LibraryStore rolled back to %s (reason=%s)", commit_hash, reason
        )

    def clear_active(self, *, reason: str = "") -> None:
        """Wipe every active skill directory + reset manifest.yaml to empty.

        Used by ``library_scope == "environment"`` baselines to isolate
        each environment's skills. The previous env's library tree is
        recoverable via git history (every patch was committed) and the
        per-env snapshot tag (``after-<env_id>``) recorded by the hook
        before this call.

        Refuses while ``.frozen`` exists -- the eval block must always
        unfreeze before any mutation. The hook orchestrates this:
        ``unfreeze_and_maintain`` runs FIRST, then ``clear_active``,
        then the next env's first task triggers ``inject_curated`` /
        ``induce_skill`` which re-populate from scratch.
        """
        if self.is_frozen():
            raise PermissionError("clear_active called while frozen")

        if self.active_dir.exists():
            for child in list(self.active_dir.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                elif child.is_file():
                    # Defensive: any stray top-level file (none expected
                    # under the slug-as-folder convention).
                    child.unlink()

        # Empty manifest -- subsequent has_seed_for / has_curated_for
        # calls return False, so curated/selfgen baselines correctly
        # re-seed at the next env's T1.
        empty = LibraryManifest()
        self._save_manifest(empty)

        # Commit the wipe so audit history shows when each env started
        # fresh. ``--allow-empty`` is set by _GitWrapper.commit so this
        # produces a commit even if the working tree already had no
        # active skills (defensive idempotence).
        self._git.add_all()
        msg = "library: clear_active"
        if reason:
            msg += f" ({reason})"
        self._git.commit(msg)
        _LOG.info("LibraryStore.clear_active: %s", reason or "<no reason>")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> LibraryManifest:
        if not self.manifest_path.exists():
            return LibraryManifest()
        data = yaml.safe_load(self.manifest_path.read_text()) or {}
        return LibraryManifest.model_validate(data)

    def _save_manifest(self, manifest: LibraryManifest) -> None:
        # Pydantic's model_dump(mode="json") emits json-safe values (datetime
        # as iso strings). yaml.safe_dump then writes them back deterministically.
        self.manifest_path.write_text(
            yaml.safe_dump(
                manifest.model_dump(mode="json"),
                sort_keys=True,            # deterministic ordering for git diffs
                default_flow_style=False,
                allow_unicode=True,
            )
        )

    def _read_skill_files(self, skill_dir: Path) -> dict[str, str]:
        if not skill_dir.exists():
            return {}
        out: dict[str, str] = {}
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(skill_dir).as_posix()
            try:
                out[rel] = path.read_text()
            except UnicodeDecodeError:
                continue
        return out

    @staticmethod
    def _coerce_author(strategy_name: str) -> AuthorStrategy:
        try:
            return AuthorStrategy(strategy_name)
        except ValueError:
            # Unknown strategies still need a default for the manifest entry.
            return AuthorStrategy.CHAIN

    @staticmethod
    def _extract_descriptions_from_patch(
        patch: SkillPatch,
        slug_to_sid: dict[str, str],
    ) -> dict[str, str]:
        """Pull Tier-1 ``description`` fields out of any SKILL.md upserts.

        The retriever embeds ``entry.description`` and the prompt builder
        renders it as the agent-facing trigger text. Both must reflect the
        SKILL.md frontmatter (the actual Tier-1 spec), not ``patch.summary``
        (a git-style audit message). Returns ``{skill_id: description}`` for
        every target skill whose patch carries a SKILL.md with a parseable
        non-empty ``description``. Skills without a SKILL.md change, or with
        malformed frontmatter, are simply omitted -- callers fall back to
        the existing entry's description (or ``patch.summary`` for first
        creation).
        """
        from skillevolbench.discovery import parse_skill_md_frontmatter_text
        out: dict[str, str] = {}
        for rel_path, content in patch.upsert_files.items():
            if not rel_path.endswith("/SKILL.md"):
                continue
            slug = rel_path.split("/", 1)[0]
            sid = slug_to_sid.get(slug)
            if sid is None:
                continue
            try:
                fm = parse_skill_md_frontmatter_text(content, source=rel_path)
            except ValueError as exc:
                _LOG.warning(
                    "SKILL.md frontmatter unparseable for %s: %s", sid, exc,
                )
                continue
            desc = fm.get("description")
            if isinstance(desc, str) and desc.strip():
                out[sid] = desc.strip()
        return out

    @staticmethod
    def _new_manifest_entry(
        skill_id: str,
        patch: SkillPatch,
        current_task: str,
        author: AuthorStrategy,
        description: Optional[str] = None,
    ) -> SkillManifestEntry:
        return SkillManifestEntry(
            skill_id=skill_id,
            name=skill_id.split(".", 1)[-1],
            family_id=skill_id.split(".", 1)[0],
            current_version=1,
            status=SkillStatus.ACTIVE,
            applicability=Applicability(),
            evidence=SkillEvidence(),
            # Prefer SKILL.md frontmatter description; fall back to
            # patch.summary only when the patch carries no parseable
            # SKILL.md (defensive -- should not happen for well-formed
            # creations).
            description=description or patch.summary,
            created_at_task=current_task,
            last_revised_at_task=current_task,
            versions=[
                SkillVersionRecord(
                    version=1,
                    patch_id=patch.patch_id,
                    created_at_task=current_task,
                    parent_version=None,
                    author_strategy=author,
                    summary=patch.summary,
                )
            ],
        )

    @staticmethod
    def _bump_existing_skill(
        entry: SkillManifestEntry,
        patch: SkillPatch,
        current_task: str,
        author: AuthorStrategy,
        new_description: Optional[str] = None,
    ) -> None:
        prev = entry.current_version
        entry.current_version = prev + 1
        entry.last_revised_at_task = current_task
        # When the revision rewrote SKILL.md, refresh the manifest
        # description so the retriever sees the latest Tier-1 trigger
        # text. Skills whose patch only touched scripts/references/assets
        # leave description untouched.
        if new_description:
            entry.description = new_description
        # IMPORTANT: do NOT reset entry.status here. The status (RETIRED /
        # QUARANTINED) is set by the deletes-step or by explicit lifecycle
        # patches (operation_type=RETIRE/QUARANTINE). Resetting to ACTIVE
        # here would silently revive retired skills on every revision.
        # Explicit revival should be done via a fresh CREATE / REPLACE patch.
        entry.versions.append(
            SkillVersionRecord(
                version=prev + 1,
                patch_id=patch.patch_id,
                created_at_task=current_task,
                parent_version=prev,
                author_strategy=author,
                summary=patch.summary,
            )
        )

    @staticmethod
    def _uuid() -> str:
        import uuid
        return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# NullLibrary -- used when baseline.use_skill_library is False
# ---------------------------------------------------------------------------


class NullLibrary:
    """A drop-in replacement that silently swallows all writes.

    No-Skill / Raw-Trajectory-RAG / History-Context-Control baselines build
    a ``BaselineRuntime`` with ``library = NullLibrary()`` so the hook can
    call ``runtime.library.compute_hash()`` etc. without conditionals.
    """

    def __init__(self):
        self._sentinel_hash = "null-library-no-mutation"

    def compute_hash(self) -> str:
        return self._sentinel_hash

    def list_active(self) -> list[SkillManifestEntry]:
        return []

    def list_skill_ids(self) -> list[str]:
        return []

    def has_skill(self, skill_id: str) -> bool:
        return False

    def has_seed_for(self, family_id: str) -> bool:
        return False

    def has_curated_for(self, family_id: str) -> bool:
        return False

    def is_frozen(self) -> bool:
        return False

    def freeze(self) -> None: ...
    def unfreeze(self) -> None: ...

    def apply_patch(self, *args, **kwargs) -> ApplyResult:
        raise PermissionError("NullLibrary does not accept patches")

    def inject_curated(self, *args, **kwargs) -> ApplyResult:
        raise PermissionError("NullLibrary cannot inject curated")

    def create_skill(self, *args, **kwargs) -> ApplyResult:
        raise PermissionError("NullLibrary cannot create skills")

    def get_manifest_entry(self, skill_id: str) -> SkillManifestEntry:
        raise KeyError(skill_id)

    def get_skill(self, skill_id: str) -> SkillVersion:
        raise KeyError(skill_id)

    def skills_in_family(self, family_id: str) -> list[SkillManifestEntry]:
        return []

    def rollback_to(self, *args, **kwargs) -> None: ...

    def clear_active(self, *, reason: str = "") -> None:
        """No-op: NullLibrary has no active skills to clear."""
        return None


__all__ = ["LibraryStore", "NullLibrary"]
