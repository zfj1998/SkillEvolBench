# Fixture Plan: E1-LS3-T5

Role: `adversarial`
Gap focus: `Gap 1 trap: each stage has a distinct empty-input meaning.`

Scenario:
A seemingly clean refactor encourages the shortcut `if not input: return None`, but the three pipeline stages intentionally treat `None`, `{}`, and empty strings differently.

Intended fixture files:
- `pipeline.py`
- `public_tests/test_pipeline.py`

Key design notes:
The fixture should make the shortcut pass most visible tests while failing hidden cases. `parse(None)` must yield `{}`, `transform(None)` must yield `None`, and `format_output(None)` must yield an empty string.

Public checks:
- Normal JSON input still works.
- Empty-string input still works.
- The refactor exposes a `Pipeline.run()` entry point.

Hidden checks:
- `parse(None)` returns `{}`.
- `transform(None)` returns `None`.
- `format_output(None)` returns an empty string.
- `run(None)` preserves the stage-by-stage semantics and yields the default-marked JSON output.
- Empty dict behavior remains distinct from `None` behavior.

Process checks:
- There is no blanket `if not input: return None` shortcut.
- Each stage keeps its own empty-input behavior.
- A `Pipeline` class exists with a `run(input)` method.
