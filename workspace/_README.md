# `workspace/`

**Runtime state. Not in version control.** Each run writes a self-contained
subdirectory under `runs/<run_id>/` -- compressing that subdirectory yields a
fully reproducible artifact bundle.

```
workspace/
└── runs/
    └── <run_id>/                 # one per (baseline x strategy x order_seed)
        ├── config.yaml           # full RunConfig (resume-able)
        ├── state.json            # run-level checkpoint
        ├── library/              # git-versioned global skill library
        │   ├── .git/
        │   ├── manifest.yaml
        │   ├── active/<skill_id>/...
        │   ├── .frozen           # marker: present iff in eval block
        │   └── snapshots/        # git tags per env transition
        ├── runtime/<task_id>/
        │   ├── harbor-task-copy/ # immutable benchmark/tasks/<slug>/ copy
        │   │   └── instruction.md  # ★ overwritten with retrieval injection
        │   └── injection-context.json
        ├── stores/
        │   ├── replay/replay.db + records/
        │   ├── events/{lifecycle,patches,system}.jsonl
        │   ├── retrieval/retrieval_events.jsonl
        │   └── snapshots/        # references into library/.git tags
        ├── harbor-job/           # Harbor's own job output
        └── reports/              # final metric reports
```

`run_id` convention: `{baseline_name}__{strategy_name}__seed{A|B|C}__{YYYYMMDD_HHMM}`.

This directory is `.gitignore`d (see top-level `.gitignore`). The internal
files are owned by:
* Part 5: `library/`, `stores/`
* Part 6: `runtime/`
* Part 9: `config.yaml`, `state.json`
* Harbor SDK: `harbor-job/`
* Part 10: `reports/`

Compress + archive policy: weekly `tar.zst` of the whole `runs/<run_id>/` is
recommended once a run completes (avoid losing replay data to accidental
cleanup).
