# Running SkillEvolBench

1. Install the package in editable mode.

```bash
pip install -e .
```

2. Validate static assets and configs.

```bash
python -m scripts.validate_assets
python -m scripts.validate_configs
```

3. Inspect the task order without launching Harbor.

```bash
skillevolbench dry-run-schedule --order-seed A
```

4. Run a scheduler/runtime dry-run.

```bash
python -m scripts.run --baseline-name no_skill --order-seed A --dry-run
```

5. For real runs, build the runtime image and run strict preflight.

```bash
bash docker/agent-build/build.sh
python -m scripts.preflight --strict
```

6. Launch one run.

```bash
python -m scripts.run --baseline-name curated_with_revision_always --order-seed A
```

Completed runs can be summarized with:

```bash
python -m scripts.summarize workspace/runs/<run_id>
```
