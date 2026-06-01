from __future__ import annotations
import json
from pathlib import Path
from dossier_loader import load_dossier
from priority_policy import rank_sections
from audience_policy import audience_focus

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

def words(text: str) -> int:
    return len(text.split())

def make_summary(sections: list[dict], limit: int = 500) -> dict:
    selected = []
    body = []
    for section in rank_sections(sections)[:3]:
        sentence = section["summary"]
        if words(" ".join(body + [sentence])) <= limit:
            body.append(sentence)
            selected.append(section["id"])
    return {"text": " ".join(body), "selected_sections": selected, "word_count": words(" ".join(body))}

def main():
    dossier = load_dossier()
    mode = "hierarchical"
    if mode == "multi_audience":
        summaries = {}
        for audience in ["technical", "management", "client"]:
            _ = audience_focus(audience)
            summaries[audience] = make_summary(dossier["sections"], 300)
        result = {"summaries": summaries}
    elif mode == "hierarchical":
        article_summaries = [make_summary(article["sections"], 200) for article in dossier["articles"]]
        result = {
            "article_summaries": article_summaries,
            "group_summaries": [make_summary([s for a in dossier["articles"] for s in a["sections"]], 300)],
            "overall_summary": make_summary([s for a in dossier["articles"] for s in a["sections"]], 500),
        }
    else:
        result = make_summary(dossier["sections"], 500)
    (OUTPUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
