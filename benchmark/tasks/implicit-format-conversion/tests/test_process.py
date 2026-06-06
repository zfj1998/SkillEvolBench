
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "project" / "make_readable.py").read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_not_just_json_code_fence(self):
        bad = "```json" in SOURCE and "json.dumps(data, indent=2)" in SOURCE and "table" not in SOURCE.lower()
        self.assertFalse(bad, "expected a true readability transformation, not just pretty-printing")

    def test_process_preserves_data_from_multiple_sections(self):
        self.assertTrue(any(token in SOURCE.lower() for token in ["teams", "services", "settings", "summary"]))

if __name__ == "__main__":
    unittest.main()
