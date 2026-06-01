from __future__ import annotations
def choose_best(sources):
    return sorted(sources, key=lambda s: (s["publisher"] == "Stanford HAI", s["evidence_strength"] == "high"), reverse=True)[0]
