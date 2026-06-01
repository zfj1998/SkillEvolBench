
import pandas as pd
from pathlib import Path

from formula_capture import write_loss_report
from workbook_manifest import EXPECTED_SHEETS

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "sales_workbook.xlsx"
OUTPUT_DIR = ROOT / "output"

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    df = pd.read_excel(INPUT)
    df.to_csv(OUTPUT_DIR / "Data.csv", index=False)
    write_loss_report(OUTPUT_DIR, [{"sheet": "Reference", "note": "not exported in starter"}, {"sheet": "Summary", "note": "formula values not exported"}])

if __name__ == "__main__":
    main()
