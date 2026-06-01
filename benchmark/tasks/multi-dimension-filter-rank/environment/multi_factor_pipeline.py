    from __future__ import annotations
    import json
    from pathlib import Path
    from source_loader import load_sources
    from ranking_policy import score

    ROOT = Path(__file__).resolve().parent
    OUTPUT = ROOT / "output"
    OUTPUT.mkdir(exist_ok=True)

    def main():
        ranked = sorted(load_sources(), key=score, reverse=True)[:5]
        result = {"selected": [s["id"] for s in ranked]}
        (OUTPUT / "selection.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (OUTPUT / "summary.md").write_text("# Summary

Selected top sources.
", encoding="utf-8")

    if __name__ == "__main__":
        main()
