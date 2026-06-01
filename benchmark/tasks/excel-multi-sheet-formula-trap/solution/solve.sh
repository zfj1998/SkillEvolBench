#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/convert_excel.py" <<'__SKILL_EVOL_REFERENCE_CONVERT_EXCEL_PY_0__'
import pandas as pd
from pathlib import Path

from formula_capture import write_loss_report
from workbook_manifest import EXPECTED_SHEETS

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "sales_workbook.xlsx"
OUTPUT_DIR = ROOT / "output"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    sheets = pd.read_excel(INPUT, sheet_name=None)
    for name, df in sheets.items():
        df.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
    write_loss_report(OUTPUT_DIR, [])


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_CONVERT_EXCEL_PY_0__
