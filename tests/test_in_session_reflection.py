from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.baselines.runtime import BaselineRuntime
from skillevolbench.components.in_session_reflection import (
    InSessionSkillReflection,
    ReflectionCandidateError,
)
from skillevolbench.schemas import (
    FailedTest,
    RunConfig,
    StrategyConfig,
    TrialOutcome,
)


TASK = SimpleNamespace(
    task_id="E1-LS1-T1",
    family_id="E1-LS1",
    primary_skill="E1-LS1.systematic-error-diagnosis",
    latent_skill_id="E1-LS1.systematic-error-diagnosis",
    role="canonical",
)


class _Library:
    def __init__(self, skill_ids: list[str] | None = None) -> None:
        self.skill_ids = skill_ids or []

    def has_seed_for(self, family_id: str) -> bool:
        return any(skill_id.startswith(f"{family_id}.") for skill_id in self.skill_ids)

    def skills_in_family(self, family_id: str):
        return [
            SimpleNamespace(skill_id=skill_id)
            for skill_id in self.skill_ids
            if skill_id.startswith(f"{family_id}.")
        ]


def _outcome(*, passed: bool = False) -> TrialOutcome:
    return TrialOutcome(
        task_id=TASK.task_id,
        verifier_passed=passed,
        reward=1.0 if passed else 0.0,
        failed_tests=(
            []
            if passed
            else [
                FailedTest(
                    name="hidden_null_case",
                    message="expected None to be handled",
                    group="outcome",
                )
            ]
        ),
    )


def _skill_md(slug: str) -> str:
    return (
        "---\n"
        f"name: {slug}\n"
        "description: Use when diagnosing a reproducible runtime failure.\n"
        "---\n\n"
        "# Diagnostic workflow\n\nInspect the error and validate the fix.\n"
    )


def _write_candidate(path: Path, upserts: dict[str, str], **extra) -> None:
    payload = {
        "summary": "distill the observed diagnostic workflow",
        "operation_type": "create",
        "upsert_files": upserts,
        "delete_paths": [],
        **extra,
    }
    path.write_text(json.dumps(payload))


def test_requested_baseline_is_explicit_same_session_setting() -> None:
    baseline = load_baseline("selfgen_in_session_always")

    assert baseline.skill_update_source == "same_agent_session"
    assert baseline.harbor_agent_name == "opencode"
    assert baseline.revision_trigger == "always"
    assert baseline.retriever_type == "embedding"
    assert baseline.within_env_replay is False


def test_same_session_runtime_does_not_construct_host_skill_author(
    tmp_path: Path,
) -> None:
    baseline = load_baseline("selfgen_in_session_always")
    strategy = StrategyConfig.from_yaml("configs/strategies/chain.yaml")
    runtime = BaselineRuntime.build(
        RunConfig(
            run_id="same-session-no-author",
            baseline=baseline,
            strategy=strategy,
            environment_id="E1",
            workspace_root=tmp_path,
        )
    )

    assert runtime.evolver is None
    assert runtime.host_llm_clients == []


def test_trigger_matrix_induces_then_revises_pass_and_fail() -> None:
    baseline = load_baseline("selfgen_in_session_always")
    empty = InSessionSkillReflection(baseline=baseline, library=_Library())
    seeded = InSessionSkillReflection(
        baseline=baseline,
        library=_Library(["E1-LS1.systematic-error-diagnosis"]),
    )

    assert empty.plan(TASK, _outcome()) == (True, "induction")
    assert seeded.plan(TASK, _outcome()) == (True, "revision")
    assert seeded.plan(TASK, _outcome(passed=True)) == (True, "revision")

    eval_task = SimpleNamespace(**{**TASK.__dict__, "role": "context-shift"})
    assert seeded.plan(eval_task, _outcome()) == (False, "not_learning_role")


def test_induction_candidate_becomes_host_owned_patch(tmp_path: Path) -> None:
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())
    candidate = tmp_path / "candidate.json"
    slug = "systematic-error-diagnosis"
    _write_candidate(candidate, {f"{slug}/SKILL.md": _skill_md(slug)})

    patch = reflection.parse_candidate(
        candidate,
        task=TASK,
        outcome=_outcome(),
        mode="induction",
    )

    assert patch is not None
    assert patch.target_skill_ids == [TASK.primary_skill]
    assert patch.triggered_by_task == TASK.task_id
    assert patch.proposing_mode == "in_session_reflection"
    assert patch.patch_id


@pytest.mark.parametrize(
    ("raw_path", "reason"),
    [
        ("../escape/SKILL.md", "candidate_path_unsafe"),
        ("/absolute/SKILL.md", "candidate_path_unsafe"),
        ("systematic-error-diagnosis\\SKILL.md", "candidate_path_backslash"),
        ("systematic-error-diagnosis/other/file.txt", "candidate_path_outside_skill_layout"),
    ],
)
def test_candidate_rejects_unsafe_paths(
    tmp_path: Path,
    raw_path: str,
    reason: str,
) -> None:
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, {raw_path: _skill_md("systematic-error-diagnosis")})

    with pytest.raises(ReflectionCandidateError, match=reason):
        reflection.parse_candidate(
            candidate,
            task=TASK,
            outcome=_outcome(),
            mode="induction",
        )


def test_candidate_rejects_bad_native_skill_frontmatter(tmp_path: Path) -> None:
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())
    candidate = tmp_path / "candidate.json"
    slug = "systematic-error-diagnosis"
    _write_candidate(
        candidate,
        {f"{slug}/SKILL.md": "---\nname: wrong\n---\n\n# Body\n"},
    )

    with pytest.raises(
        ReflectionCandidateError,
        match="skill_frontmatter_name_mismatch|skill_frontmatter_invalid",
    ):
        reflection.parse_candidate(
            candidate,
            task=TASK,
            outcome=_outcome(),
            mode="induction",
        )


def test_candidate_accepts_native_frontmatter_with_unquoted_colon(
    tmp_path: Path,
) -> None:
    """The reflection gate must accept what native skill discovery accepts."""
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())
    candidate = tmp_path / "candidate.json"
    slug = "systematic-error-diagnosis"
    _write_candidate(
        candidate,
        {
            f"{slug}/SKILL.md": (
                "---\n"
                f"name: {slug}\n"
                "description: Use for diagnosis. Symptoms: repeated failures.\n"
                "---\n\n"
                "# Systematic error diagnosis\n"
            )
        },
    )

    patch = reflection.parse_candidate(
        candidate,
        task=TASK,
        outcome=_outcome(),
        mode="induction",
    )

    assert patch is not None
    assert patch.target_skill_ids == [str(TASK.primary_skill)]


def test_candidate_rejects_known_credential_literal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())
    candidate = tmp_path / "candidate.json"
    slug = "systematic-error-diagnosis"
    secret = "sk-test-secret-123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    _write_candidate(
        candidate,
        {f"{slug}/SKILL.md": _skill_md(slug) + f"\nToken: {secret}\n"},
    )

    with pytest.raises(
        ReflectionCandidateError,
        match="candidate_contains_secret:OPENAI_API_KEY",
    ):
        reflection.parse_candidate(
            candidate,
            task=TASK,
            outcome=_outcome(),
            mode="induction",
        )


def test_prompt_discloses_feedback_but_forbids_tests_and_direct_writes() -> None:
    baseline = load_baseline("selfgen_in_session_always")
    reflection = InSessionSkillReflection(baseline=baseline, library=_Library())

    prompt, feedback = reflection.build_prompt(TASK, _outcome(), mode="induction")

    assert feedback["verifier_passed"] is False
    assert feedback["failed_tests"][0]["name"] == "hidden_null_case"
    assert "/tests" in prompt
    assert "Do not look for or run verifier tests" in prompt
    assert "/logs/agent/self_reflection_patch.json" in prompt
    assert "Do not modify `/root/task`" in prompt
    assert "Transfer-quality contract" in prompt
    assert "different inputs" in prompt
    assert "access to this verifier feedback" in prompt
    assert "distributions/counts/sets" in prompt
    assert "Examples must be synthetic or generalized" in prompt
