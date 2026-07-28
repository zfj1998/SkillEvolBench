
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "project"
SOURCE = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (
        PROJECT / "pipeline.py",
        PROJECT / "pdf_extract.py",
        PROJECT / "json_bridge.py",
        PROJECT / "docx_writer.py",
    )
    if path.exists()
)

class ProcessTests(unittest.TestCase):
    def test_process_has_three_stage_pipeline(self):
        self.assertTrue("extract" in SOURCE and "JSON_OUT" in SOURCE and "build_docx" in SOURCE)

    def test_process_extracts_profit_and_builds_table(self):
        lowered = SOURCE.lower()
        self.assertTrue("profit" in lowered and "add_table" in lowered,
                        "expected profit extraction plus a structured DOCX table")

if __name__ == "__main__":
    unittest.main()
