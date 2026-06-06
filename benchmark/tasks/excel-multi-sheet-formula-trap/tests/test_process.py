
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "project" / "convert_excel.py").read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_reads_all_sheets_not_default_single_sheet(self):
        self.assertTrue("sheet_name=None" in SOURCE or "load_workbook" in SOURCE or ".sheetnames" in SOURCE)

    def test_process_computes_or_loads_formula_values_for_summary(self):
        lowered = SOURCE.lower()
        self.assertTrue(any(token in lowered for token in ["data_only", "expected_summary", "openpyxl", "formula", "calculate"]),
                        "expected explicit handling of formula values rather than writing formula text")

if __name__ == "__main__":
    unittest.main()
