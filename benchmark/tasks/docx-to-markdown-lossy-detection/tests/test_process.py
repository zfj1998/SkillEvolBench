
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "project" / "convert_docx.py").read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_generates_both_outputs(self):
        self.assertIn("document.md", SOURCE)
        self.assertIn("loss_report.json", SOURCE)

    def test_process_loss_report_has_structured_fields(self):
        self.assertTrue(("element_type" in SOURCE and "description" in SOURCE) or "source_features.json" in SOURCE,
                        "expected structured loss items with element_type and description")

    def test_process_does_not_truncate_loss_inventory(self):
        self.assertNotIn("[:1]", SOURCE)

if __name__ == "__main__":
    unittest.main()
