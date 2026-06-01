# Repository Surface

This repository is organized around the start-to-run benchmark framework.

- Keep: benchmark assets, configs, runtime/orchestration code, public launchers,
  validation scripts, and single-run summarization.
- Exclude: generated analysis, paper figures, local run outputs, temporary smoke
  scripts, and old experimental scaffolds that are not wired into the public run
  path.

The supported public CLI commands are:

```bash
skillevolbench validate-assets
skillevolbench validate-configs
skillevolbench dry-run-schedule
skillevolbench run
skillevolbench summarize
skillevolbench launch-main
skillevolbench launch-multi-model
```
