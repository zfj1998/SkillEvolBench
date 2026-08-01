from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "experiments/full_180_quality_audit/build_audit.py"
SPEC = importlib.util.spec_from_file_location("build_full_180_quality_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_generated_skill_update_is_linked_to_later_new_input_use() -> None:
    payload = {
        "skills": [{
            "skill_id": "E1-LS1.example",
            "created_at_task": "E1-LS1-T2",
            "last_revised_at_task": "E1-LS1-T2",
            "current_version": 1,
            "generated_path": "library/example/SKILL.md",
        }],
        "evaluation": [{
            "task_id": "E1-LS1-T4",
            "skills_actually_used": ["E1-LS1.example"],
        }],
    }

    result = AUDIT.generated_skill_reuse(payload, "E1-LS1-T2")

    assert [row["skill_id"] for row in result["skill_updates"]] == [
        "E1-LS1.example"
    ]
    assert result["later_evaluation_uses"] == [{
        "task_id": "E1-LS1-T4",
        "skill_ids": ["E1-LS1.example"],
    }]


def test_current_no_skill_pass_is_only_a_single_run_low_demand_screen() -> None:
    result = AUDIT.check_need(
        5,
        [{"category": "history_supported"}],
        [],
        {"no_skill": {"outcome_pass": True}},
    )

    assert result["status"] == "v1_1_single_run_low_skill_demand"
    assert "majority" in result["claim_boundary"]


def test_unrelated_skill_evidence_never_uses_curated_all_as_a_substitute() -> None:
    result = AUDIT.check_unrelated(6)

    assert result["status"] == "missing_strict_shuffled_curated_control"
    assert "curated-all" in result["claim_boundary"]
