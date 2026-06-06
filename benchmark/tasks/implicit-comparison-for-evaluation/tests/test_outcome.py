from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "evaluation.json"
def setup_module():
    subprocess.run([sys.executable, "evaluation_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_output(self):
        assert OUTPUT.exists()
    def test_multiple_dimensions(self):
        dims = json.loads(OUTPUT.read_text())["dimensions"]
        assert len(dims) >= 5
    def test_has_recommendation(self):
        assert "recommendation" in json.loads(OUTPUT.read_text())

    def test_dimensions_have_evidence(self):
        dims = json.loads(OUTPUT.read_text())["dimensions"]
        assert all(isinstance(dim, dict) and dim.get("evidence") for dim in dims)

    def test_recommendation_has_basis(self):
        data = json.loads(OUTPUT.read_text())
        basis = data.get("rationale") or data.get("recommendation", {}).get("basis") if isinstance(data.get("recommendation"), dict) else data.get("rationale")
        assert isinstance(basis, str) and len(basis.strip()) > 10

    def test_dimension_names_present(self):
        dims = json.loads(OUTPUT.read_text())["dimensions"]
        assert all(isinstance(dim.get("name"), str) and dim["name"].strip() for dim in dims)
