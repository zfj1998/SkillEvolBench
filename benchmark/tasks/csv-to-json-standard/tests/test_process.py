
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "project" / "convert_csv.py").read_text(encoding="utf-8")
INFER = (Path(__file__).resolve().parents[1] / "project" / "type_inference.py").read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_has_explicit_id_handling_rule(self):
        self.assertTrue(
            ('key == "id"' in INFER or "key == 'id'" in INFER or "STRING_FIELDS" in INFER),
            "expected an explicit field-specific rule for id to preserve leading zeros"
        )

    def test_process_handles_thousands_separator_before_float_cast(self):
        self.assertTrue("," in INFER and ("replace" in INFER or "translate" in INFER),
                        "expected explicit thousands-separator cleanup before float parsing")

if __name__ == "__main__":
    unittest.main()
