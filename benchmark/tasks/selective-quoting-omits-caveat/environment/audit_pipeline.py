from __future__ import annotations
import json
from pathlib import Path
from source_loader import load_citations, load_sources
from citation_policy import classify_citation

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def main():
    sources = load_sources()
    results = []
    for citation in load_citations():
        source = sources.get(citation.get("source_id"))
        result = classify_citation(citation, source)
        results.append({
            "citation_id": citation["citation_id"],
            "source_id": citation.get("source_id"),
            "article_claim": citation["article_claim"],
            "label": result["label"],
            "checks": result.get("checks", []),
            "reason": result.get("reason", ""),
        })
    summary = {
        "audited_count": len(results),
        "labels": {label: sum(1 for item in results if item["label"] == label) for label in sorted({item["label"] for item in results})},
        "results": results,
    }
    (OUTPUT / "citation_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
