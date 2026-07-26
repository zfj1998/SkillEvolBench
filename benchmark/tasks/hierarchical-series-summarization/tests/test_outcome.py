from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "summary.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([sys.executable, "summarizer.py"], cwd=ROOT, check=True)

def data():
    return json.loads(OUTPUT.read_text(encoding="utf-8"))

def text_blocks(obj):
    if "text" in obj:
        return [obj["text"]]
    blocks = []
    if "summaries" in obj:
        blocks.extend(item["text"] for item in obj["summaries"].values())
    if "article_summaries" in obj:
        blocks.extend(item["text"] for item in obj["article_summaries"])
    if "group_summaries" in obj:
        blocks.extend(item["text"] for item in obj["group_summaries"])
    if "overall_summary" in obj:
        blocks.append(obj["overall_summary"]["text"])
    return blocks


def concept_present(term, text):
    patterns = {
        "validation": r"\bvalidat(?:e|ed|es|ing|ion)\b",
        "skin": r"\bskin\b|\bdermatolog\w*\b",
    }
    return bool(re.search(patterns.get(term.lower(), re.escape(term.lower())), text))


def group_summary_for(obj, theme):
    for item in obj.get("group_summaries", []):
        text = item.get("text", "").lower()
        selected = " ".join(item.get("selected_sections", [])).lower()
        if theme in text or f"_{theme}_" in selected:
            return item
    return None


class TestOutcome:
    def test_output_exists(self):
        assert OUTPUT.exists()

    def test_word_limits(self):
        obj = data()
        if "text" in obj:
            assert obj["word_count"] <= GT["limits"]["single"]
        if "summaries" in obj:
            for audience, item in obj["summaries"].items():
                assert item["word_count"] <= GT["limits"]["audience"]
        if "article_summaries" in obj:
            for item in obj["article_summaries"]:
                assert item["word_count"] <= GT["limits"]["article"]
            for item in obj["group_summaries"]:
                assert item["word_count"] <= GT["limits"]["group"]
            assert obj["overall_summary"]["word_count"] <= GT["limits"]["overall"]

    def test_required_concepts_present(self):
        joined = " ".join(text_blocks(data())).lower()
        for term in GT["required_terms"]:
            assert concept_present(term, joined), term

    def test_forbidden_terms_absent(self):
        joined = " ".join(text_blocks(data())).lower()
        for term in GT.get("forbidden_terms", []):
            assert term.lower() not in joined, term

    def test_priority_selection(self):
        obj = data()
        selected = []
        if "selected_sections" in obj:
            selected.extend(obj["selected_sections"])
        if "summaries" in obj:
            for item in obj["summaries"].values():
                selected.extend(item["selected_sections"])
        if "article_summaries" in obj:
            for item in obj["article_summaries"]:
                selected.extend(item["selected_sections"])
            for item in obj["group_summaries"]:
                selected.extend(item["selected_sections"])
            selected.extend(obj["overall_summary"]["selected_sections"])
        for sid in GT["must_select"]:
            assert sid in selected, sid

    def test_audience_or_hierarchy_shape(self):
        obj = data()
        if GT["shape"] == "multi_audience":
            assert set(obj["summaries"]) == {"technical", "management", "client"}
            texts = {k: v["text"].lower() for k, v in obj["summaries"].items()}
            assert "architecture" in texts["technical"] or "latency" in texts["technical"]
            assert "roi" in texts["management"] or "payback" in texts["management"]
            assert "user" in texts["client"] or "launch" in texts["client"]
        elif GT["shape"] == "hierarchical":
            assert len(obj["article_summaries"]) == 5
            assert len(obj["group_summaries"]) == 2
            assert group_summary_for(obj, "method") is not None
            assert group_summary_for(obj, "application") is not None
