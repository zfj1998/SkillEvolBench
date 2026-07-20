"""Same-session, post-verifier skill reflection.

This component contains no model client.  The task agent is resumed by the
Harbor integration after the official verifier has completed, and writes one
candidate JSON document under ``/logs/agent``.  The host parses that document
into a :class:`SkillPatch`; only the normal freeze controller may apply it.

Keeping prompt construction and candidate validation here makes the security
boundary explicit: the resumed agent never receives hidden test sources and
never gets write access to the active skill library.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from skillevolbench.schemas import FeedbackLevel, OperationType, SkillPatch
from skillevolbench.stores.library_store import skill_id_to_slug


REFLECTION_CANDIDATE_FILENAME = "self_reflection_patch.json"
REFLECTION_FEEDBACK_FILENAME = "self_reflection_feedback.json"
REFLECTION_PROMPT_FILENAME = "self_reflection_prompt.md"
REFLECTION_RESULT_FILENAME = "self_reflection_result.json"

_LEARNING_ROLES = frozenset({"canonical", "enriched", "variant"})
_SAFE_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
)
_MAX_CANDIDATE_BYTES = 1_000_000
_MAX_FILE_BYTES = 500_000
_MAX_TOTAL_CONTENT_BYTES = 900_000
_SECRET_ENV_NAMES = frozenset(
    {
        "MODEL_API_KEY",
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AP_API_KEY",
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
)


class ReflectionCandidateError(ValueError):
    """The model returned a scoreable but unusable reflection candidate."""


@dataclass
class ReflectionRecord:
    """Host-side audit record cached until ``on_trial_ended``."""

    status: str
    task_id: str
    mode: str | None = None
    session_id: str | None = None
    solve_session_id: str | None = None
    reflection_session_id: str | None = None
    same_session_verified: bool = False
    patch: SkillPatch | None = None
    reason: str = ""
    prompt_path: Path | None = None
    feedback_path: Path | None = None
    candidate_path: Path | None = None
    solve_trajectory_path: Path | None = None
    full_session_trajectory_path: Path | None = None
    solve_session_export_path: Path | None = None
    full_session_export_path: Path | None = None
    prompt_sha256: str | None = None
    solve_trajectory_sha256: str | None = None
    full_session_trajectory_sha256: str | None = None
    solve_session_export_sha256: str | None = None
    full_session_export_sha256: str | None = None
    task_workspace_hash_before: str | None = None
    task_workspace_hash_after: str | None = None
    trajectory_prefix_verified: bool = False
    export_prefix_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "task_id": self.task_id,
            "mode": self.mode,
            "session_id": self.session_id,
            "solve_session_id": self.solve_session_id,
            "reflection_session_id": self.reflection_session_id,
            "same_session_verified": self.same_session_verified,
            "patch_id": self.patch.patch_id if self.patch else None,
            "reason": self.reason,
            "prompt_path": str(self.prompt_path) if self.prompt_path else None,
            "feedback_path": (
                str(self.feedback_path) if self.feedback_path else None
            ),
            "candidate_path": (
                str(self.candidate_path) if self.candidate_path else None
            ),
            "solve_trajectory_path": (
                str(self.solve_trajectory_path)
                if self.solve_trajectory_path
                else None
            ),
            "full_session_trajectory_path": (
                str(self.full_session_trajectory_path)
                if self.full_session_trajectory_path
                else None
            ),
            "solve_session_export_path": (
                str(self.solve_session_export_path)
                if self.solve_session_export_path
                else None
            ),
            "full_session_export_path": (
                str(self.full_session_export_path)
                if self.full_session_export_path
                else None
            ),
            "prompt_sha256": self.prompt_sha256,
            "solve_trajectory_sha256": self.solve_trajectory_sha256,
            "full_session_trajectory_sha256": (
                self.full_session_trajectory_sha256
            ),
            "solve_session_export_sha256": self.solve_session_export_sha256,
            "full_session_export_sha256": self.full_session_export_sha256,
            "task_workspace_hash_before": self.task_workspace_hash_before,
            "task_workspace_hash_after": self.task_workspace_hash_after,
            "trajectory_prefix_verified": self.trajectory_prefix_verified,
            "export_prefix_verified": self.export_prefix_verified,
        }


class InSessionSkillReflection:
    """Build and validate the second turn of a learning trial."""

    def __init__(self, *, baseline: Any, library: Any) -> None:
        self.baseline = baseline
        self.library = library

    def plan(self, task: Any, outcome: Any) -> tuple[bool, str]:
        """Return ``(should_reflect, mode_or_reason)``.

        The trigger mirrors ``ChainEvolution``: induce on an empty T1 family,
        otherwise revise according to ``revision_trigger``.  Evaluation,
        shadow and replay trials are filtered by the hook before this method.
        """
        role = self._role(task)
        if role not in _LEARNING_ROLES:
            return False, "not_learning_role"

        family_id = str(task.family_id)
        has_seed = bool(self.library.has_seed_for(family_id))
        # A malformed/noop T1 candidate must not permanently brick the family.
        # If the family is still empty, the next distinct learning input may
        # recover by inducing the same primary skill.
        if self.baseline.allow_self_gen_induction and not has_seed:
            return True, "induction"

        if not self.baseline.allow_revision:
            return False, "revision_disabled"
        trigger = getattr(self.baseline, "revision_trigger", "never")
        if trigger == "never":
            return False, "revision_trigger_never"
        if trigger == "fail_only" and bool(outcome.verifier_passed):
            return False, "trigger_fail_only_but_passed"
        return True, "revision"

    def feedback_payload(self, task: Any, outcome: Any, *, mode: str) -> dict[str, Any]:
        """Return the bounded verifier feedback disclosed to the model."""
        level = FeedbackLevel(getattr(self.baseline, "feedback_level", "none"))
        payload: dict[str, Any] = {
            "task_id": str(task.task_id),
            "family_id": str(task.family_id),
            "role": self._role(task),
            "reflection_mode": mode,
        }
        if level == FeedbackLevel.NONE:
            payload["feedback"] = "withheld_by_setting"
            return payload

        payload["verifier_passed"] = bool(outcome.verifier_passed)
        if level == FeedbackLevel.BINARY:
            return payload

        payload.update(
            {
                "reward": float(outcome.reward),
                "outcome_passed": outcome.outcome_passed,
                "process_passed": outcome.process_passed,
                "failed_tests": [
                    {
                        "group": str(getattr(item, "group", ""))[:40],
                        "name": str(getattr(item, "name", ""))[:200],
                        "message": self._bounded_text(
                            str(getattr(item, "message", "")), 500
                        ),
                    }
                    for item in list(outcome.failed_tests or [])[:12]
                ],
            }
        )
        if level == FeedbackLevel.PROCESS:
            payload["rubric_dimensions"] = [
                {
                    "name": str(getattr(item, "name", ""))[:120],
                    "tests_matched": int(getattr(item, "tests_matched", 0) or 0),
                    "tests_passed": int(getattr(item, "tests_passed", 0) or 0),
                    "score": float(getattr(item, "score", 0.0) or 0.0),
                }
                for item in list(outcome.rubric_dimensions or [])[:20]
            ]
        return payload

    def build_prompt(self, task: Any, outcome: Any, *, mode: str) -> tuple[str, dict[str, Any]]:
        """Build the verifier-feedback turn sent to the original session."""
        feedback = self.feedback_payload(task, outcome, mode=mode)
        primary_id = str(task.primary_skill)
        primary_slug = skill_id_to_slug(primary_id)
        family_entries = list(self.library.skills_in_family(str(task.family_id)))
        existing = [str(entry.skill_id) for entry in family_entries]
        existing_slugs = [skill_id_to_slug(skill_id) for skill_id in existing]

        if mode == "induction":
            operation = (
                f"Create the first reusable skill for `{primary_id}`. The patch "
                f"must include `{primary_slug}/SKILL.md`."
            )
            allowed = (
                f"All upsert paths must stay under `{primary_slug}/` and may use "
                "only SKILL.md, scripts/, references/, or assets/."
            )
        else:
            listed = ", ".join(f"`{slug}`" for slug in existing_slugs) or "(none)"
            operation = (
                "Improve the current family skill from the reusable evidence in "
                "the preceding solve turn. Existing family skill slugs: " + listed + "."
            )
            allowed = (
                "Revise an existing family slug, or add one clearly distinct sibling "
                f"slug in family `{task.family_id}`. Use only SKILL.md, scripts/, "
                "references/, or assets/."
            )

        prompt = f"""# Post-verifier self-reflection

You are continuing the exact same session in which you just attempted task
`{task.task_id}`. The official verifier has now run. Reflect on your actual
approach in the preceding turn together with the bounded verifier feedback
below, then distill a reusable skill update that should help on related but
different future inputs. Do not merely memorize this task's literal answer.

{operation}

Verifier feedback:

```json
{json.dumps(feedback, indent=2, ensure_ascii=False)}
```

The active library is readable at `/skills/`; inspect the relevant existing
SKILL.md before proposing a revision. `{allowed}` Every SKILL.md must start
with YAML frontmatter containing at least `name` and a concrete `description`
that says when the skill should be used.

Security and state boundary:

- Do not look for or run verifier tests. `/tests` and raw verifier logs are
  intentionally unavailable; only the bounded feedback above is authorized.
- Do not modify `/root/task`, `/workspace`, `/skills`, or any native skill mount.
- Never include credentials, tokens, endpoint secrets, or environment values in
  the candidate.
- The only file you may create or modify is
  `/logs/agent/{REFLECTION_CANDIDATE_FILENAME}`.
- This is a candidate only. The host will validate it and decide whether to
  update the shared library after this session ends.

Write exactly one UTF-8 JSON object to that file using this shape:

```json
{{
  "summary": "one-line reusable lesson",
  "operation_type": "{('create' if mode == 'induction' else 'revise')}",
  "upsert_files": {{
    "{primary_slug}/SKILL.md": "---\\nname: ...\\ndescription: ...\\n---\\n\\n# ...\\n"
  }},
  "delete_paths": []
}}
```

JSON must parse without fences or comments. After writing it, read the file
back once to check it. Your final response should briefly state what reusable
lesson you encoded; do not include another copy of the JSON.
"""
        return prompt, feedback

    def parse_candidate(
        self,
        path: Path,
        *,
        task: Any,
        outcome: Any,
        mode: str,
    ) -> SkillPatch | None:
        """Parse and strictly constrain the agent-authored candidate."""
        path = Path(path)
        if not path.is_file():
            raise ReflectionCandidateError("candidate_file_missing")
        if path.stat().st_size > _MAX_CANDIDATE_BYTES:
            raise ReflectionCandidateError("candidate_file_too_large")
        try:
            data = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReflectionCandidateError("candidate_json_invalid") from exc
        if not isinstance(data, dict):
            raise ReflectionCandidateError("candidate_must_be_object")
        return self._parse_candidate_data(
            data, task=task, outcome=outcome, mode=mode
        )

    def parse_candidate_bytes(
        self,
        raw: bytes,
        *,
        task: Any,
        outcome: Any,
        mode: str,
    ) -> SkillPatch | None:
        """Parse a candidate captured from one already-opened, nofollow fd."""
        if len(raw) > _MAX_CANDIDATE_BYTES:
            raise ReflectionCandidateError("candidate_file_too_large")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReflectionCandidateError("candidate_json_invalid") from exc
        if not isinstance(data, dict):
            raise ReflectionCandidateError("candidate_must_be_object")
        return self._parse_candidate_data(
            data, task=task, outcome=outcome, mode=mode
        )

    def _parse_candidate_data(
        self,
        data: dict[str, Any],
        *,
        task: Any,
        outcome: Any,
        mode: str,
    ) -> SkillPatch | None:
        serialized_candidate = json.dumps(data, ensure_ascii=False)
        for name in _SECRET_ENV_NAMES:
            secret = os.environ.get(name, "")
            if len(secret) >= 4 and secret in serialized_candidate:
                raise ReflectionCandidateError(
                    f"candidate_contains_secret:{name}"
                )
        if data.get("action") == "noop":
            return None

        upserts = data.get("upsert_files")
        if not isinstance(upserts, dict) or not upserts:
            raise ReflectionCandidateError("candidate_upserts_missing")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in upserts.items()):
            raise ReflectionCandidateError("candidate_upserts_must_be_strings")
        total_size = sum(len(value.encode("utf-8")) for value in upserts.values())
        if total_size > _MAX_TOTAL_CONTENT_BYTES:
            raise ReflectionCandidateError("candidate_content_too_large")
        if any(len(value.encode("utf-8")) > _MAX_FILE_BYTES for value in upserts.values()):
            raise ReflectionCandidateError("candidate_file_content_too_large")
        deletes = data.get("delete_paths", []) or []
        if deletes and not getattr(self.baseline, "allow_retirement", False):
            raise ReflectionCandidateError("delete_not_allowed_by_baseline")
        if not isinstance(deletes, list) or not all(isinstance(item, str) for item in deletes):
            raise ReflectionCandidateError("delete_paths_must_be_strings")

        family_id = str(task.family_id)
        existing_ids = [
            str(entry.skill_id) for entry in self.library.skills_in_family(family_id)
        ]
        existing_slugs = {skill_id_to_slug(skill_id) for skill_id in existing_ids}
        list_all = getattr(self.library, "list_all", None)
        all_entries = list_all() if callable(list_all) else []
        global_slug_owners = {
            skill_id_to_slug(str(entry.skill_id)): str(entry.skill_id)
            for entry in all_entries
        }
        primary_id = str(task.primary_skill)
        primary_slug = skill_id_to_slug(primary_id)
        for raw_path in list(upserts) + deletes:
            rel = self._validate_relative_path(raw_path)
            slug = rel.parts[0]
            if mode == "induction" and slug != primary_slug:
                raise ReflectionCandidateError("induction_path_outside_primary_slug")
            if mode == "revision" and slug not in existing_slugs:
                # A new sibling is allowed, but its slug must form a valid
                # same-family latent id and it must carry its own SKILL.md.
                if f"{slug}/SKILL.md" not in upserts:
                    raise ReflectionCandidateError(
                        f"new_sibling_missing_skill_md:{family_id}.{slug}"
                    )
                owner = global_slug_owners.get(slug)
                expected = f"{family_id}.{slug}"
                if owner is not None and owner != expected:
                    raise ReflectionCandidateError(
                        f"candidate_slug_owned_by_other_family:{owner}"
                    )

        # The model-authored markdown becomes a native agent skill on the next
        # task, so validate its discovery metadata before it reaches git.
        for raw_path, content in upserts.items():
            if not raw_path.endswith("/SKILL.md"):
                continue
            slug = raw_path.split("/", 1)[0]
            try:
                frontmatter = self._strict_frontmatter(content)
            except (TypeError, ValueError, yaml.YAMLError) as exc:
                raise ReflectionCandidateError(
                    f"skill_frontmatter_invalid:{slug}"
                ) from exc
            if str(frontmatter.get("name", "")).strip() != slug:
                raise ReflectionCandidateError(
                    f"skill_frontmatter_name_mismatch:{slug}"
                )
            if not str(frontmatter.get("description", "")).strip():
                raise ReflectionCandidateError(
                    f"skill_frontmatter_description_missing:{slug}"
                )

        if mode == "induction" and f"{primary_slug}/SKILL.md" not in upserts:
            raise ReflectionCandidateError("induction_missing_skill_md")

        touched_slugs = {
            raw_path.split("/", 1)[0] for raw_path in [*upserts, *deletes]
        }
        if mode == "induction":
            target_skill_ids = [primary_id]
            operation_type = OperationType.CREATE
        else:
            if not existing_ids:
                raise ReflectionCandidateError("revision_has_no_existing_skill")
            new_slugs = sorted(
                {
                    raw_path.split("/", 1)[0]
                    for raw_path in upserts
                    if raw_path.split("/", 1)[0] not in existing_slugs
                }
            )
            existing_by_slug = {
                skill_id_to_slug(skill_id): skill_id for skill_id in existing_ids
            }
            touched_existing_ids = [
                existing_by_slug[slug]
                for slug in sorted(touched_slugs & existing_slugs)
            ]
            target_skill_ids = touched_existing_ids + [
                f"{family_id}.{slug}" for slug in new_slugs
            ]
            operation_type = (
                OperationType.CREATE if new_slugs else OperationType.REVISE
            )

        patch = SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=str(data.get("summary", "(no summary)"))[:200],
            upsert_files=dict(upserts),
            delete_paths=list(deletes),
            target_skill_ids=target_skill_ids,
            operation_type=operation_type,
            triggered_by_task=str(task.task_id),
            triggered_by_failure_type=self._classify_failure(
                str(outcome.failure_summary or "")
            ),
            proposing_mode="in_session_reflection",
            attempt_count=1,
        )

        if any(not skill_id.startswith(f"{family_id}.") for skill_id in patch.target_skill_ids):
            raise ReflectionCandidateError("candidate_cross_family_target")
        if patch.operation_type not in {
            OperationType.CREATE.value,
            OperationType.REVISE.value,
        }:
            raise ReflectionCandidateError("candidate_operation_not_allowed")
        return patch

    @staticmethod
    def _strict_frontmatter(content: str) -> dict[str, Any]:
        normalized = content.replace("\r\n", "\n")
        if not normalized.startswith("---\n"):
            raise ValueError("missing opening YAML delimiter")
        end = normalized.find("\n---\n", 4)
        if end < 0:
            raise ValueError("missing closing YAML delimiter")
        loaded = yaml.safe_load(normalized[4:end])
        if not isinstance(loaded, dict):
            raise ValueError("frontmatter must be a mapping")
        unknown = set(loaded) - _ALLOWED_FRONTMATTER_KEYS
        if unknown:
            raise ValueError(f"unsupported frontmatter keys: {sorted(unknown)}")
        for key in ("name", "description"):
            if not isinstance(loaded.get(key), str):
                raise TypeError(f"frontmatter {key} must be a string")
        for key in ("license", "compatibility"):
            if key in loaded and not isinstance(loaded[key], str):
                raise TypeError(f"frontmatter {key} must be a string")
        if "metadata" in loaded and not isinstance(loaded["metadata"], dict):
            raise TypeError("frontmatter metadata must be a mapping")
        if "allowed-tools" in loaded and not isinstance(
            loaded["allowed-tools"], (str, list)
        ):
            raise TypeError("frontmatter allowed-tools must be a string or list")
        return loaded

    @staticmethod
    def _validate_relative_path(raw_path: str) -> PurePosixPath:
        if "\\" in raw_path or "\x00" in raw_path:
            raise ReflectionCandidateError("candidate_path_backslash")
        rel = PurePosixPath(raw_path)
        if rel.is_absolute() or ".." in rel.parts or len(rel.parts) < 2:
            raise ReflectionCandidateError("candidate_path_unsafe")
        slug = rel.parts[0]
        if not _SAFE_SLUG_RE.fullmatch(slug):
            raise ReflectionCandidateError("candidate_slug_invalid")
        tail = rel.parts[1:]
        if tail == ("SKILL.md",):
            return rel
        if tail[0] not in {"scripts", "references", "assets"} or len(tail) < 2:
            raise ReflectionCandidateError("candidate_path_outside_skill_layout")
        if any(
            part in {"", ".", ".."} or "\x00" in part
            for part in tail
        ):
            raise ReflectionCandidateError("candidate_path_unsafe")
        return rel

    @staticmethod
    def _role(task: Any) -> str:
        role = getattr(task, "role", "")
        return str(getattr(role, "value", role))

    @staticmethod
    def _bounded_text(text: str, limit: int) -> str:
        # Avoid control characters in a prompt/artifact while preserving
        # ordinary newlines and tabs in diagnostic messages.
        clean = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
        return clean[:limit]

    @staticmethod
    def _classify_failure(summary: str) -> str | None:
        """Keep patch metadata useful without invoking the legacy author."""
        if not summary:
            return None
        lowered = summary.lower()
        if "import" in lowered or "modulenotfound" in lowered:
            return "import_error"
        if "type" in lowered:
            return "type_error"
        if "key" in lowered:
            return "key_error"
        if "timeout" in lowered:
            return "timeout"
        if "process" in lowered or "shortcut" in lowered:
            return "process_failure"
        return "outcome_failure"


__all__ = [
    "InSessionSkillReflection",
    "ReflectionCandidateError",
    "ReflectionRecord",
    "REFLECTION_CANDIDATE_FILENAME",
    "REFLECTION_FEEDBACK_FILENAME",
    "REFLECTION_PROMPT_FILENAME",
    "REFLECTION_RESULT_FILENAME",
]
