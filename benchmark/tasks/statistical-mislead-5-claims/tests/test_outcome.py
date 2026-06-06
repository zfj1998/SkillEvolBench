from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "claim_review.json"
CLAIMS = json.loads((ROOT / "claim_packets.json").read_text())
def setup_module():
    subprocess.run([sys.executable, "claim_audit.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_reviews_all_claims(self):
        assert len(json.loads(OUTPUT.read_text())["reviews"]) == 5
    def test_marks_most_as_misleading(self):
        labels = [r["label"] for r in json.loads(OUTPUT.read_text())["reviews"]]
        assert labels.count("misleading") >= 4
    def test_has_specific_corrections(self):
        for review in json.loads(OUTPUT.read_text())["reviews"]:
            assert len(review["correction"]) > 20

    def test_corrections_use_source_context(self):
        reviews = {review["id"]: review["correction"].lower() for review in json.loads(OUTPUT.read_text())["reviews"]}
        expected_terms = {
            "CL1": ["absolute", "base", "market"],
            "CL2": ["sample", "methods"],
            "CL3": ["inflation", "baseline"],
            "CL4": ["comparator", "pool"],
            "CL5": ["window", "historical"],
        }
        for claim_id, terms in expected_terms.items():
            correction = reviews.get(claim_id, "")
            missing = [term for term in terms if term not in correction]
            assert not missing, f"{claim_id} correction missing source-context terms: {missing}"
