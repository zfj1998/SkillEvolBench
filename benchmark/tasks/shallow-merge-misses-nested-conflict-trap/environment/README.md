# T5 Starter Notes

This task is built to punish "looks identical enough" shortcuts.

The current starter has two layers:

- `top_level_gate.py` decides whether a record looks safe to skip
- `deep_compare.py` can do recursive comparison

The bug is architectural, not syntactic: the orchestrator trusts the top-level gate too
much, so the deep comparator never sees the records that actually matter.
