#!/usr/bin/env python3
"""Classify whether a failed AP episode may be retried from clean state.

This is intentionally stricter than a generic process retry. SkillEvolBench
has an evolving, environment-scoped skill library, so a retry must restart the
whole environment episode and must never reuse the failed attempt's workspace.
Only a structured, unscoreable agent timeout is currently retryable. Ordinary
verifier failures are scientific outcomes and therefore never enter this path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


RETRYABLE_REASON = "agent-or-runtime-exception"
RETRYABLE_EXCEPTION_TYPE = "AgentTimeoutError"


def classify_episode_retry(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable, credential-free retry decision."""

    status = metrics.get("status")
    scoreable = metrics.get("scoreable")
    error_reason = metrics.get("error_reason")
    exception_type = metrics.get("error_exception_type")
    retryable = (
        status == "failed"
        and scoreable is False
        and error_reason == RETRYABLE_REASON
        and exception_type == RETRYABLE_EXCEPTION_TYPE
    )

    if retryable:
        decision_reason = "structured-agent-timeout"
    elif status != "failed":
        decision_reason = "episode-is-not-failed"
    elif scoreable is not False:
        decision_reason = "failure-is-not-explicitly-unscoreable"
    elif error_reason != RETRYABLE_REASON:
        decision_reason = "failure-reason-is-not-retryable"
    else:
        decision_reason = "exception-type-is-not-retryable"

    return {
        "schema_version": "1.0",
        "retryable": retryable,
        "decision_reason": decision_reason,
        "environment_id": metrics.get("environment_id"),
        "error_task_id": metrics.get("error_task_id"),
        "error_reason": error_reason,
        "error_exception_type": exception_type,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="episode metrics.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "retryable": False,
                    "decision_reason": "metrics-are-unreadable",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 2
    if not isinstance(payload, dict):
        print(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "retryable": False,
                    "decision_reason": "metrics-root-is-not-an-object",
                },
                sort_keys=True,
            )
        )
        return 2

    decision = classify_episode_retry(payload)
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["retryable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
