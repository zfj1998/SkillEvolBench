from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "selection.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())
def setup_module():
    subprocess.run([sys.executable, "multi_factor_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_selection(self):
        assert OUTPUT.exists()
    def test_excludes_irrelevant(self):
        sel = json.loads(OUTPUT.read_text())["selected"]
        assert not (set(sel) & set(GT["must_exclude"]))
    def test_prefers_core_sources(self):
        sel = json.loads(OUTPUT.read_text())["selected"]
        assert len(set(sel) & set(GT["preferred"])) >= 4
    def test_has_summary(self):
        assert (ROOT / "output" / "summary.md").exists()
