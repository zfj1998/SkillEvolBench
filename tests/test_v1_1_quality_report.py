from __future__ import annotations

from scripts.ap.build_v1_1_quality_report import heatmap_summary, render_html


def test_heatmap_summary_requires_and_totals_all_108_cells() -> None:
    records = []
    for model in ["qwen3.7-max", "sig-fable", "opus-4.8"]:
        for environment in range(1, 7):
            for tier in range(1, 7):
                records.append(
                    {
                        "model": model,
                        "environment_id": f"E{environment}",
                        "tier": tier,
                        "observed": 5,
                        "strict": 3,
                        "outcome": 4,
                        "process": 4,
                    }
                )
    result = heatmap_summary(records)
    assert result["totals"]["opus-4.8"] == {
        "strict": 108,
        "outcome": 144,
        "process": 144,
        "observed": 180,
    }


def test_report_is_standalone_and_explains_claim_boundary() -> None:
    data = {
        "generated_at_utc": "2026-07-27T00:00:00+00:00",
        "model_order": [],
        "model_zh": {},
        "heatmap": {"records": [], "totals": {}},
        "behavior": {},
        "behavior_takeaways": [
            {"title": "verifier 定向措辞", "body": "measurement boundary"}
        ],
        "task_audit": {},
        "reference_audit": {},
        "regression": {},
        "measurement_validity": {},
        "protocol_design": {},
        "claim_boundary": "Skill reads prove utilization, not causal usefulness.",
    }
    rendered = render_html(data)
    assert "<!doctype html>" in rendered
    assert "Skill utilization" in rendered
    assert "no-skill" in rendered
    assert "Skill rescue" in rendered
    assert "matched tasks" in rendered
    assert "关键术语" in rendered
    assert "整族退役" in rendered
    assert "完整 SKILL.md" in rendered
    assert "verifier 定向措辞" in rendered
    assert "Skill reads prove utilization, not causal usefulness." in rendered
