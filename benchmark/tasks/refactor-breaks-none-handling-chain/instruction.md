# Refactor the parse/transform/format chain without collapsing empty-input behavior

The pipeline code is in `/root/task`. We want the current three-step flow turned into a `Pipeline` class with a `run()` entry point, but the existing stages intentionally do not treat `None`, `{}`, and empty strings the same way.

Please refactor the existing implementation in place and preserve the exact stage-by-stage behavior:
- `parse`, `transform`, and `format_output` must keep their own boundary semantics
- `run_pipeline(None)` still needs to reflect the current chained behavior
- keep the CLI-facing behavior stable

Start here:
- `/root/task/README.md`
- `/root/task/docs/serialization-notes.md`
- `/root/task/pipeline.py`
- `/root/task/legacy_formatter.py`
- `/root/task/cli_wrapper.py`

Save your edits under `/root/task`. Do not move the project elsewhere or replace the implementation with a stub.
