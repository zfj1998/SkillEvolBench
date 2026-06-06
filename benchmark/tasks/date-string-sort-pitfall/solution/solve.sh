#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "ordering_policy.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def sort_logs(df: pd.DataFrame) -> pd.DataFrame:
            return df.sort_values(["parsed_date", "time", "log_id"], kind="mergesort").reset_index(drop=True)
        """
    ),
    "process_logs.py": dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path

        import pandas as pd

        from date_parser import parse_display_dates
        from ordering_policy import sort_logs

        CSV_PATH = Path("server_logs.csv")
        OUTPUT_PATH = Path("output.json")


        def run(csv_path: Path = CSV_PATH, output_path: Path = OUTPUT_PATH) -> dict:
            df = pd.read_csv(csv_path)
            df["parsed_date"] = parse_display_dates(df["date"])
            sorted_df = sort_logs(df)
            export_df = sorted_df.drop(columns=["parsed_date"], errors="ignore")
            payload = {
                "row_count": int(len(export_df)),
                "first_date": export_df.iloc[0]["date"],
                "last_date": export_df.iloc[-1]["date"],
                "records": export_df.to_dict(orient="records"),
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


        if __name__ == "__main__":
            run()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
