# Environment Plan: E2-LS2-T4

Role: `context-shift`
Gap focus: `Retry is implicit inside a larger 5-step sync workflow.`

Scenario:
The sync pipeline runs `auth -> list -> detail -> enrich -> save`. The detail stage can fail transiently. The client should recover without repeating valid upstream work.

Starter files:
- `pipeline_client.py`
- `mock_pipeline.py`
- `docs/pipeline-runbook.md`

Key design notes:
The fragile version retries a coarse pipeline stage instead of retrying the failing detail request precisely.
