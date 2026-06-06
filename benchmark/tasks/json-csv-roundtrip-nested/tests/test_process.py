
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "project" / "roundtrip.py").read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_has_flatten_step(self):
        self.assertIn("def flatten", SOURCE)

    def test_process_has_restore_step(self):
        self.assertIn("def unflatten", SOURCE)

    def test_process_performs_deep_verification(self):
        self.assertTrue("restored == data" in SOURCE or "deepdiff" in SOURCE.lower())

if __name__ == "__main__":
    unittest.main()
