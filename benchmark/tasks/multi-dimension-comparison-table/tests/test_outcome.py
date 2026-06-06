from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "comparison.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())
def setup_module():
    subprocess.run([sys.executable, "comparison_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_table(self):
        assert OUTPUT.exists()
    def test_covers_most_dimensions(self):
        dims = [row["dimension"] for row in json.loads(OUTPUT.read_text())["rows"]]
        overlap = len(set(dims) & set(GT["required_dimensions"]))
        assert overlap >= 6
    def test_sources_attached(self):
        for row in json.loads(OUTPUT.read_text())["rows"]:
            assert row["sources"]

    def test_output_schema_conforms(self):
        payload = json.loads(OUTPUT.read_text())
        assert set(payload) == {"rows"}
        assert isinstance(payload["rows"], list) and len(payload["rows"]) >= 6
        for row in payload["rows"]:
            assert isinstance(row.get("dimension"), str) and row["dimension"]
            assert isinstance(row.get("sources"), list) and row["sources"]

    def test_rows_compare_both_crms_and_choose_winner(self):
        payload = json.loads(OUTPUT.read_text())
        compared = 0
        allowed_winners = {"salesforce", "hubspot", "tie", "insufficient_evidence"}
        for row in payload["rows"]:
            crm_a = row.get("crm_a")
            crm_b = row.get("crm_b")
            winner = row.get("winner")
            if crm_a is None and crm_b is None and winner is None:
                continue
            assert isinstance(crm_a, str) and crm_a.strip(), f"{row.get('dimension')} missing crm_a comparison"
            assert isinstance(crm_b, str) and crm_b.strip(), f"{row.get('dimension')} missing crm_b comparison"
            assert winner in allowed_winners, f"{row.get('dimension')} has invalid winner {winner!r}"
            compared += 1
        assert compared >= 6, "at least six dimensions must compare both CRM products, not only list sources"
