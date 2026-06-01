# configs/

Configuration files consumed by the SkillEvolBench run harness.

| Path | Purpose |
| --- | --- |
| `baselines/*.yaml` | Baseline capability presets. The canonical set is registered in `skillevolbench.baselines.policy`. |
| `strategies/*.yaml` | Revision strategy presets (`chain`, `chain_tier3`). |
| `models/*.yaml` | Optional model routing presets for `scripts.run` and multi-model sweeps. |
| `env_orders.yaml` | Environment order seeds A/B/C used by the scheduler. |
| `llm.yaml` | Default host-side LLM endpoint settings. |

All files in this directory are data. Matching Pydantic schemas live in
`skillevolbench/schemas/` and are validated with:

```bash
python -m scripts.validate_configs
```
