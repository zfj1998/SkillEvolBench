"""Validate the static-asset layer of SkillEvolBench.

Run before any benchmark run -- a non-zero exit means the static assets are
broken and any subsequent run is invalid.

Checks include:
* 30 skill families and 180 tasks present, fully indexed
* meta.yaml + task-spec.yaml schema validates (via Pydantic models)
* SKILL.md frontmatter is well-formed (YAML or permissive fallback)
* task.toml [metadata] consistent with task-spec.yaml
* T6 required_skills point to existing families
* every task Dockerfile inherits from agent-runtime:latest
* tests/test.sh exists in every task
* agents_port package importable with the expected adapter classes
* (optional) agent-runtime image present in the local container builder

Pass ``--strict-image`` to fail when the agent-runtime image is missing in
docker/podman; otherwise the missing image is reported as a warning.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.discovery import (  # noqa: E402
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
    parse_task_toml_metadata,
)
from skillevolbench.schemas.task import (  # noqa: E402
    ENV_SLUG_TO_ID,
    ROLE_TO_INDEX,
    ROLE_TO_PHASE,
    TaskRole,
)


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    n_families: int = 0
    n_tasks: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_AGENT_RUNTIME_FROM_RE = re.compile(
    r"^\s*FROM\s+agent-runtime(?::[A-Za-z0-9_.\-]+)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _check_dockerfile(report: ValidationReport, dockerfile: Path, tag: str) -> None:
    if not dockerfile.exists():
        report.fail(f"{tag}: missing Dockerfile at {dockerfile}")
        return
    text = dockerfile.read_text()
    if not _AGENT_RUNTIME_FROM_RE.search(text):
        report.fail(
            f"{tag}: Dockerfile must FROM agent-runtime[:tag]; got first line "
            f"{text.splitlines()[0] if text.splitlines() else '(empty)'!r}"
        )


_VERIFIER_OUTPUT_CONTRACT: tuple[tuple[str, str], ...] = (
    # filename, severity ("error" | "warn")
    ("reward.txt", "error"),         # canonical Harbor reward signal
    ("score_report.json", "warn"),   # rubric dimensions consumed by VerifierAdapter
    ("outcome_report.json", "warn"), # outcome group used for T5 trap detection
    ("process_report.json", "warn"), # process group used for T5 shortcut detection
)


def _check_test_sh(report: ValidationReport, test_sh: Path, tag: str) -> None:
    """Verify the task ships ``tests/test.sh`` and writes the verifier-output
    contract files we rely on at runtime.

    Severity rules:
      * ``reward.txt`` missing -> hard error (Harbor verifier requirement).
      * any other expected output missing -> warning. Part 6 ``VerifierAdapter``
        degrades gracefully when these are absent (only outcome/process splits
        and rubric dimensions are unavailable for that task), but the warning
        flags drift from the contract documented in PART1_STATIC_ASSETS.md
        §1.6.
    """
    if not test_sh.exists():
        report.fail(f"{tag}: missing tests/test.sh at {test_sh}")
        return
    text = test_sh.read_text()
    for filename, severity in _VERIFIER_OUTPUT_CONTRACT:
        if filename in text:
            continue
        msg = (
            f"{tag}: tests/test.sh does not write {filename} "
            f"(verifier-output contract: see docs/PART1_STATIC_ASSETS.md §1.6)"
        )
        if severity == "error":
            report.fail(msg)
        else:
            report.warn(msg)


def _check_agents_port(report: ValidationReport) -> None:
    try:
        sys.path.insert(0, str(REPO_ROOT))
        import agents_port  # noqa: F401
    except Exception as exc:
        report.warn(
            f"agents_port: package not importable ({exc!r}); Part 4 Harbor agent "
            f"registration will fail until it is fixed"
        )
        return
    expected_modules = ["agents_port.preinstalled", "agents_port.openclaw"]
    for mod_name in expected_modules:
        try:
            __import__(mod_name)
        except Exception as exc:
            report.warn(
                f"agents_port: cannot import {mod_name!r} ({exc!r}); the harbor "
                f"agent classes referenced by JobConfig.agents may be missing"
            )
            return
    # Confirm at least one Preinstalled class is exported
    from agents_port import preinstalled  # type: ignore
    expected = ["ClaudeCodePreinstalled", "CodexPreinstalled",
                "GeminiCliPreinstalled", "KimiCliPreinstalled",
                "OpenCodePreinstalled"]
    missing = [name for name in expected if not hasattr(preinstalled, name)]
    if missing:
        report.warn(
            f"agents_port.preinstalled is missing expected classes: {missing}"
        )


def _check_harbor_ext(report: ValidationReport) -> None:
    """Verify Part 4 import boundaries:
    * ``skillevolbench.harbor_ext`` (top + types + hooks) MUST import without Harbor.
    * ``harbor_ext.env`` and ``harbor_ext.job_builder`` are Harbor-dependent;
      they are expected to import iff harbor is installed.
    """
    try:
        from skillevolbench import harbor_ext  # noqa: F401
        from skillevolbench.harbor_ext import (
            SkillEvolBenchHooks,  # noqa: F401
            RuntimeProtocol,      # noqa: F401
            harbor_available,
        )
    except Exception as exc:
        report.fail(
            f"skillevolbench.harbor_ext top-level import broken (must succeed "
            f"without Harbor SDK): {exc!r}"
        )
        return

    has_harbor = harbor_available()
    for mod in ("skillevolbench.harbor_ext.env", "skillevolbench.harbor_ext.job_builder"):
        try:
            __import__(mod)
            imported = True
        except ImportError:
            imported = False
        except Exception as exc:
            report.fail(
                f"{mod}: import raised non-ImportError ({exc!r}); "
                f"only ImportError is expected when Harbor is missing"
            )
            continue

        if has_harbor and not imported:
            report.fail(
                f"{mod}: Harbor SDK is installed but module failed to import"
            )
        if not has_harbor and imported:
            report.warn(
                f"{mod}: imported successfully without Harbor SDK -- "
                f"check that the module's hard imports are still in place"
            )


def _check_agent_runtime_image(
    report: ValidationReport, strict: bool, tag: str = "agent-runtime:latest"
) -> None:
    """Probe whether agent-runtime image exists in docker or podman."""
    builder = shutil.which("docker") or shutil.which("podman")
    if not builder:
        report.warn(
            "no docker/podman binary on PATH -- skipping agent-runtime presence "
            "check (docker/agent-build/build.sh must succeed before any run)"
        )
        return
    proc = subprocess.run(
        [builder, "image", "inspect", tag],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (
            f"agent-runtime image {tag!r} not found via {builder!r}; build it "
            f"with `docker/agent-build/build.sh` before running the benchmark"
        )
        if strict:
            report.fail(msg)
        else:
            report.warn(msg)


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------


def validate_all_assets(
    skills_root: Path,
    tasks_root: Path,
    *,
    strict_image: bool = False,
) -> ValidationReport:
    report = ValidationReport()

    if not skills_root.exists():
        report.fail(f"skills_root does not exist: {skills_root}")
        return report
    if not tasks_root.exists():
        report.fail(f"tasks_root does not exist: {tasks_root}")
        return report

    # --- Load full registry; Pydantic validates every meta.yaml/task-spec.yaml ---
    try:
        registry = TaskRegistry.from_disk(skills_root, tasks_root)
    except Exception as exc:
        report.fail(f"registry loading failed: {exc}")
        return report

    report.n_families = len(registry.families)
    report.n_tasks = len(registry.tasks)

    if report.n_families != 30:
        report.fail(f"expected 30 skill families, got {report.n_families}")
    if report.n_tasks != 180:
        report.fail(f"expected 180 tasks, got {report.n_tasks}")

    # --- Family-level checks ---
    family_ids: set[str] = set()
    skill_slugs: set[str] = set()
    latent_skill_ids: set[str] = set()
    for fam in registry.families:
        if fam.meta.family_id in family_ids:
            report.fail(f"duplicate family_id: {fam.meta.family_id}")
        family_ids.add(fam.meta.family_id)
        if fam.slug in skill_slugs:
            report.fail(f"duplicate skill slug: {fam.slug}")
        skill_slugs.add(fam.slug)
        latent_skill_ids.add(fam.meta.latent_skill_id)
        # SKILL.md must exist and have non-empty body
        skill_md = fam.folder / "SKILL.md"
        if not skill_md.exists():
            report.fail(f"{fam.meta.family_id}: missing SKILL.md")
            continue
        body_after_fm = skill_md.read_text().split("---", 2)[-1].strip()
        if not body_after_fm:
            report.warn(
                f"{fam.meta.family_id}: SKILL.md has no body after frontmatter"
            )

    # 6 environments, each with 5 families
    env_to_families: dict[str, list[str]] = {}
    for fam in registry.families:
        env_to_families.setdefault(fam.meta.environment_id, []).append(fam.meta.family_id)
    for env_id in [f"E{i}" for i in range(1, 7)]:
        n = len(env_to_families.get(env_id, []))
        if n != 5:
            report.fail(f"environment {env_id}: expected 5 families, got {n}")

    # --- Task-level checks ---
    task_ids: set[str] = set()
    task_slugs: set[str] = set()
    family_to_task_ids: dict[str, set[str]] = {fid: set() for fid in family_ids}
    for t in registry.tasks:
        if t.spec.task_id in task_ids:
            report.fail(f"duplicate task_id: {t.spec.task_id}")
        task_ids.add(t.spec.task_id)
        if t.slug in task_slugs:
            report.fail(f"duplicate task slug: {t.slug}")
        task_slugs.add(t.slug)
        family_to_task_ids.setdefault(t.spec.family_id, set()).add(t.spec.task_id)

        # task.toml & task-spec.yaml agreement (cross-checked in TaskRegistry,
        # but we also verify role-specific invariants here).
        idx_from_role = ROLE_TO_INDEX[t.spec.role]
        if t.spec.task_id != f"{t.spec.family_id}-T{idx_from_role}":
            report.fail(
                f"{t.spec.task_id}: task_id does not match role {t.spec.role.value}"
                f" (expected {t.spec.family_id}-T{idx_from_role})"
            )
        if t.spec.phase != ROLE_TO_PHASE[t.spec.role]:
            report.fail(
                f"{t.spec.task_id}: phase mismatch (role={t.spec.role.value}, "
                f"phase={t.spec.phase.value})"
            )

        # task-spec.yaml environment_id must match task.toml environment slug
        expected_env = ENV_SLUG_TO_ID[t.toml_metadata.environment]
        if t.spec.environment_id != expected_env:
            report.fail(
                f"{t.spec.task_id}: environment_id mismatch (spec={t.spec.environment_id}, "
                f"toml says {expected_env})"
            )

        # Required Harbor assets
        instr = t.folder / t.spec.harbor.instruction
        if not instr.exists():
            report.fail(f"{t.spec.task_id}: missing instruction at {instr}")
        _check_dockerfile(report, t.folder / t.spec.harbor.environment / "Dockerfile",
                          tag=t.spec.task_id)
        _check_test_sh(report, t.folder / t.spec.harbor.tests / "test.sh", tag=t.spec.task_id)

        # T6 required_skills must point to known families
        if t.spec.role == TaskRole.COMPOSITION:
            for sid in t.spec.required_skills:
                if sid not in latent_skill_ids:
                    report.fail(
                        f"{t.spec.task_id}: required_skill {sid!r} not found in skill library"
                    )

    # Each family has exactly 6 task ids
    for fid, ids in family_to_task_ids.items():
        expected = {f"{fid}-T{i}" for i in range(1, 7)}
        if ids != expected:
            report.fail(
                f"family {fid}: tasks mismatch. missing={sorted(expected - ids)}, "
                f"extra={sorted(ids - expected)}"
            )

    # --- agent-runtime / agents_port integration ---
    _check_agents_port(report)
    _check_harbor_ext(report)
    _check_agent_runtime_image(report, strict=strict_image)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skills-root", type=Path, default=default_skills_root())
    p.add_argument("--tasks-root", type=Path, default=default_tasks_root())
    p.add_argument(
        "--strict-image",
        action="store_true",
        help="fail when agent-runtime:latest is not present in docker/podman",
    )
    args = p.parse_args(argv)

    rep = validate_all_assets(
        args.skills_root, args.tasks_root, strict_image=args.strict_image
    )

    if rep.errors:
        print(f"x {len(rep.errors)} error(s):")
        for e in rep.errors:
            print(f"   - {e}")
    if rep.warnings:
        print(f"! {len(rep.warnings)} warning(s):")
        for w in rep.warnings:
            print(f"   - {w}")
    print(
        f"Summary: {rep.n_families} skill families, {rep.n_tasks} tasks "
        f"({'PASS' if rep.ok else 'FAIL'})"
    )
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
