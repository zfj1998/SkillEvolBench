"""PromptBuilder -- assemble the runtime ``instruction.md``.

Inputs:

* the immutable benchmark instruction text
* the BaselineConfig
* the TaskSpec (so we can use task_id / role for hints)
* retrieved skills (top-k, may be empty)
* retrieved past trajectories (control baseline only)
* history context string (control baseline only)
* a ``library_frozen`` flag

Output: the markdown text that will overwrite ``runtime/<task_id>/harbor-task-copy/instruction.md``.

Templates are inlined here as Python string literals. They're short enough
to fit in one file; if they grow we can move them to ``prompting/templates/``
and load via jinja2.

Format conventions:

* The original instruction is always rendered verbatim under ``# Task``.
* Skills are NOT listed in the prompt. Every supported agent CLI auto-
  discovers them from the bind-mounted ``/root/.<agent>/skills/`` (and
  legacy ``/skills/``) directories, so a prompt-side menu was both
  redundant and a confound: it doubled the trigger surface, displayed a
  manifest field that lagged the SKILL.md frontmatter, and -- because
  trajectories record the user message -- caused
  :class:`TrajectoryExtractor` to reverse-match injected ``/skills/<id>/``
  paths and report skills the agent never opened. ``retrieved_skills``
  is still computed upstream (for retrieval-quality metrics +
  ``injection-context.json`` audit), it just isn't surfaced to the agent.
* Trajectories / history go below the task, marked clearly as references.
* The freeze hint is rendered at the bottom with a strong directive.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from skillevolbench.schemas import BaselineConfig, RetrievedSkill


_LOG = logging.getLogger(__name__)


class PromptBuilder:
    """Stateless prompt assembler."""

    def build(
        self,
        *,
        original_instruction: str,
        baseline: BaselineConfig,
        task: Any,
        retrieved_skills: list[Any],
        retrieved_trajectories: list[Any],
        history_context: Optional[str],
        library_frozen: bool,
    ) -> str:
        """Return the injected ``instruction.md`` text."""
        # No-Skill: passthrough original instruction unchanged.
        if baseline.name == "no_skill":
            return original_instruction

        sections: list[str] = []
        sections.append(f"# Task\n\n{original_instruction.strip()}\n")

        # NOTE: ``retrieved_skills`` is intentionally NOT rendered into the
        # prompt -- agents discover skills via the container bind-mount.
        # See module docstring for rationale.
        del retrieved_skills

        if retrieved_trajectories:
            sections.append(self._format_trajectories_section(retrieved_trajectories))

        if history_context:
            sections.append(self._format_history_section(history_context))

        if library_frozen:
            sections.append(self._format_freeze_hint(baseline))
        elif baseline.use_skill_library:
            # Learning block (T1-T3): library is mutable but already
            # holds skills after T1 of any family; without this hint
            # agents tend to solve from scratch and ignore the mounted
            # skill folder. Trajectory + history baselines surface
            # their reference material via the section above; no
            # separate learning hint there (deliberate -- the Past
            # Trajectories / History sections already say "Read for
            # reference").
            sections.append(self._format_learning_skill_hint())

        return "\n".join(sections).rstrip() + "\n"

    # ------------------------------------------------------------------
    # Section formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_trajectories_section(trajs: list[Any]) -> str:
        lines = [
            "# Retrieved Past Trajectories",
            "",
            "Examples from past similar tasks. Read for reference; do not copy verbatim.",
            "",
        ]
        # Show the full compacted-trajectory text (already shrunk by
        # TrajectoryCompactor to ``max_total_tokens=8000`` per trial; with
        # reasoning_chars=3000 and observation_chars=3000 budgets a
        # typical trial lands at ~6-8K tokens). Do NOT add an extra
        # prompt-side cap -- doing so would give raw_trajectory_rag a
        # tighter signal than path-A/B baselines see in their SKILL.md
        # retrieval, which would bias the "abstraction value" comparison.
        # At T4-T6 with trajectory_retrieval_k=3, agent's instruction.md
        # carries ~24K tokens of cumulative trace evidence (3 * 8K).
        for t in trajs:
            verdict = (
                "PASSED" if getattr(getattr(t, "outcome", None), "verifier_passed", False)
                else "FAILED"
            )
            tid = getattr(t, "task_id", "?")
            # Prefer the ROUGH compaction (reasoning dropped, brief obs)
            # for raw_trajectory_rag's agent-prompt feed. This baseline's
            # whole point is "raw, unprocessed episodic experience" --
            # serving the rich compaction would silently leak the
            # reasoning-preservation + full-obs preprocessing that we
            # designed for SkillAuthor's revision input. Fall back to
            # the rich field for legacy ReplayRecords that pre-date the
            # rough field, OR for cases where rough is empty.
            rough = getattr(t, "trajectory_compact_rough", None) or {}
            rich = getattr(t, "trajectory_compact", None) or {}
            body = (rough.get("text") or rich.get("text") or "")
            lines.append(f"## Past task: {tid} ({verdict})")
            lines.append("")
            lines.append("```")
            lines.append(body)
            lines.append("```")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_history_section(history_context: str) -> str:
        return (
            "# Prior History Context\n\n"
            f"{history_context.strip()}\n"
        )

    @staticmethod
    def _format_learning_skill_hint() -> str:
        """Soft skill-use mandate during learning trials (T1-T3).

        Differences vs ``_format_freeze_hint``:
        - No "MUST NOT modify any skill" clause -- learning trials are
          where the library evolves, but the agent itself still doesn't
          touch SKILL.md (the SkillAuthor on the host writes patches
          based on the trajectory after the trial ends).
        - Acknowledges the library may be empty (T1 of the very first
          family in an env) so the wording is "if any skills are
          available", not an unconditional mandate.
        - Same mount-paths block so the agent knows where to look on
          its native CLI.
        """
        return (
            "# Skill Library\n\n"
            "A shared skill library is mounted at `/skills/` (also at "
            "your CLI's native skill folder, e.g. `/root/.claude/skills/`, "
            "`/root/.gemini/skills/`, `/root/.agents/skills/`).\n"
            "\n"
            "**BEFORE writing any solution code, you MUST:**\n"
            "\n"
            "1. List the library: `ls /skills/` (or your native folder).\n"
            "2. For each skill folder, read its `SKILL.md` and inspect the\n"
            "   YAML frontmatter `description` field.\n"
            "3. If any `description`'s 'when to use' plausibly matches this\n"
            "   task -> read the full `SKILL.md` body and FOLLOW its\n"
            "   workflow / gotchas. Use cited Tier-3 files (`scripts/`,\n"
            "   `references/`, `assets/`) per the SKILL.md instructions.\n"
            "4. Only solve from scratch if the library is empty or every\n"
            "   description is clearly unrelated -- in that case, briefly\n"
            "   state which skills you considered and why none applied.\n"
            "\n"
            "Skipping this step and reinventing a workflow that an existing\n"
            "skill already encodes wastes the library's accumulated\n"
            "knowledge. Your trajectory will be reviewed for skill use.\n"
        )

    @staticmethod
    def _format_freeze_hint(baseline: BaselineConfig) -> str:
        """Eval-block framing, branched by which reference material the
        baseline actually surfaces.

        A library-mandate hint would be nonsense for raw_trajectory_rag
        (its library is empty) or history_context_control (likewise) --
        and worse, would silently bias the abstraction-value comparison
        (selfgen vs raw_RAG). If only the library baselines see "USE the
        skills", their eval_sr gains a framing boost that trajectory
        baselines don't, so the SR delta no longer measures content
        quality alone. Each baseline must get a mandate matching the
        material it actually injects.

        We don't list specific slugs / file paths here: agents discover
        skills via bind-mounts (``/skills/`` + per-CLI native paths) and
        trajectories live in the immediately-preceding prompt section.
        """
        if baseline.use_skill_library:
            return (
                "# Evaluation Constraint\n\n"
                "This is an **evaluation** task. The skill library is "
                "mounted at `/skills/` (also at your CLI's native skill "
                "folder, e.g. `/root/.claude/skills/`, "
                "`/root/.gemini/skills/`, `/root/.agents/skills/`).\n"
                "\n"
                "**BEFORE writing any solution code, you MUST:**\n"
                "\n"
                "1. List the library: `ls /skills/`.\n"
                "2. For each skill folder, read its `SKILL.md` and inspect\n"
                "   the YAML frontmatter `description`.\n"
                "3. If any `description`'s 'when to use' matches this task\n"
                "   -> read the full `SKILL.md` body and FOLLOW its\n"
                "   workflow / gotchas. Use cited Tier-3 files\n"
                "   (`scripts/`, `references/`, `assets/`) per the\n"
                "   SKILL.md instructions.\n"
                "4. Only solve from scratch if every description is\n"
                "   clearly unrelated -- briefly state which skills you\n"
                "   considered and why none applied.\n"
                "\n"
                "You MUST NOT create, revise, retire, or modify any skill "
                "during this task.\n"
            )
        if baseline.use_trajectory_rag:
            return (
                "# Evaluation Constraint\n\n"
                "This is an **evaluation** task. The past task "
                "trajectories provided above are your reference. **Study "
                "them, identify the patterns and decisions that worked, "
                "and follow that approach** to produce your solution -- "
                "do not solve from scratch when a past trajectory "
                "suggests a relevant approach.\n"
            )
        if baseline.use_history_context:
            return (
                "# Evaluation Constraint\n\n"
                "This is an **evaluation** task. The prior history "
                "context above is your reference. **Use the patterns "
                "from that history** to produce your solution -- do not "
                "solve from scratch when the history suggests a relevant "
                "approach.\n"
            )
        # Defensive fallback: no reference material at all. (no_skill
        # bypasses the whole builder via early return, so this branch is
        # only reached if a future baseline forgets to set any of the
        # use_* flags.)
        return (
            "# Evaluation Constraint\n\n"
            "This is an **evaluation** task. Solve it using your own "
            "reasoning.\n"
        )


__all__ = ["PromptBuilder"]
