from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "comparison_matrix.json"
def setup_module():
    subprocess.run([sys.executable, "matrix_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_matrix(self):
        assert OUTPUT.exists()
    def test_missing_not_zero(self):
        rows = {row["dimension"]: row for row in json.loads(OUTPUT.read_text())["rows"]}
        assert rows["security"]["hubspot"] == "unavailable"
        assert rows["fedramp"]["hubspot"] == "unavailable"

    def test_provenance_grounding_present(self):
        data = json.loads(OUTPUT.read_text())
        provenance = data.get("provenance")
        assert isinstance(provenance, dict), "output must include a provenance block"
        assert provenance.get("method"), "provenance.method is required"
        source_ids = provenance.get("source_ids")
        assert isinstance(source_ids, list) and source_ids, "provenance.source_ids must be non-empty"
        assert all(isinstance(source_id, str) and source_id for source_id in source_ids)
