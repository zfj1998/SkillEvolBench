from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ap import classify_episode_retry as classifier


def _failed_metrics(**updates: object) -> dict[str, object]:
    metrics: dict[str, object] = {
        "status": "failed",
        "scoreable": False,
        "environment_id": "E3",
        "error_task_id": "E3-LS5-T2",
        "error_reason": "agent-or-runtime-exception",
        "error_exception_type": "AgentTimeoutError",
    }
    metrics.update(updates)
    return metrics


def test_structured_agent_timeout_is_retryable() -> None:
    decision = classifier.classify_episode_retry(_failed_metrics())

    assert decision == {
        "schema_version": "1.0",
        "retryable": True,
        "decision_reason": "structured-agent-timeout",
        "environment_id": "E3",
        "error_task_id": "E3-LS5-T2",
        "error_reason": "agent-or-runtime-exception",
        "error_exception_type": "AgentTimeoutError",
    }


@pytest.mark.parametrize(
    "metrics",
    [
        _failed_metrics(status="completed", scoreable=True),
        _failed_metrics(scoreable=True),
        _failed_metrics(error_reason="missing-verifier-result"),
        _failed_metrics(error_exception_type="RuntimeError"),
        {
            "status": "failed",
            "scoreable": False,
            "message": "Unscoreable trial E3-LS5-T2: agent timeout",
        },
    ],
)
def test_scientific_or_unstructured_failures_are_not_retryable(
    metrics: dict[str, object],
) -> None:
    assert classifier.classify_episode_retry(metrics)["retryable"] is False


def test_cli_exit_code_and_output_are_machine_readable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(_failed_metrics()), encoding="utf-8")

    assert classifier.main([str(metrics)]) == 0
    assert json.loads(capsys.readouterr().out)["retryable"] is True

    metrics.write_text("not-json", encoding="utf-8")
    assert classifier.main([str(metrics)]) == 2
    assert json.loads(capsys.readouterr().out)["retryable"] is False
